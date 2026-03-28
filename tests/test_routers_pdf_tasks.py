"""Tests for PDF tasks router."""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError

from src.routers.pdf_tasks import _validate_pdf_file, get_result, upload_pdf
from src.exceptions import DatabaseError


class TestValidatePdfFile:
    """Tests for _validate_pdf_file function."""

    def test_valid_pdf_header(self):
        """Test valid PDF magic header."""
        # PDF files start with %PDF-
        content = b"%PDF-1.4 some more content"
        assert _validate_pdf_file(content) is True

    def test_invalid_pdf_header(self):
        """Test invalid PDF magic header."""
        content = b"NOT_A_PDF_FILE"
        assert _validate_pdf_file(content) is False

    def test_empty_content(self):
        """Test empty content returns False."""
        assert _validate_pdf_file(b"") is False

    def test_too_short_content(self):
        """Test content shorter than 5 bytes returns False."""
        assert _validate_pdf_file(b"%PD") is False
        assert _validate_pdf_file(b"%PDF") is False

    def test_partial_pdf_header(self):
        """Test partial PDF header returns False."""
        assert _validate_pdf_file(b"%PDF-") is True  # Exactly 5 bytes
        assert _validate_pdf_file(b"%PDF") is False  # Only 4 bytes


class TestUploadPdf:
    """Tests for upload_pdf endpoint."""

    @pytest.mark.asyncio
    async def test_invalid_content_type(self):
        """Test rejection of non-PDF content types."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file with invalid content type
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "text/plain"
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_pdf(mock_file, mock_background)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "PDF file expected"

    @pytest.mark.asyncio
    async def test_empty_file(self):
        """Test rejection of empty file."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file that returns empty on read
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.filename = "test.pdf"
        mock_file.file = MagicMock()
        mock_file.file.read = MagicMock(return_value=b"")
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_pdf(mock_file, mock_background)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Empty file"

    @pytest.mark.asyncio
    async def test_invalid_pdf_header(self):
        """Test rejection of file with invalid PDF header."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file with invalid header
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        mock_file.file.read = MagicMock(return_value=b"NOT_PDF")
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_pdf(mock_file, mock_background)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid PDF file format"

    @pytest.mark.asyncio
    async def test_successful_upload(self):
        """Test successful PDF upload."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file with valid PDF header
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.filename = "test.pdf"
        mock_file.file = MagicMock()
        
        # Simulate reading header first, then rest of file
        pdf_content = b"%PDF-1.4 test content"
        mock_file.file.read.side_effect = [
            b"%PDF-",  # First read (header)
            b"1.4 test content",  # Second read
            b"",  # EOF
        ]
        
        with patch('src.routers.pdf_tasks.create_analysis', new_callable=AsyncMock) as mock_create:
            with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.name = "/tmp/test.pdf"
                mock_temp.return_value = mock_temp_instance
                
                result = await upload_pdf(mock_file, mock_background)
                
                # Should return task_id
                assert "task_id" in result
                assert isinstance(result["task_id"], str)
                
                # Should create analysis record
                mock_create.assert_called_once()
                
                # Should schedule background task
                mock_background.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Test rejection of oversized file."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        
        # Simulate reading header first, then large content
        from src.core.constants import MAX_FILE_SIZE
        
        mock_file.file.read.side_effect = [
            b"%PDF-",  # First read (header)
            b"x" * (MAX_FILE_SIZE + 1),  # Second read exceeds limit
        ]
        
        with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp_instance = MagicMock()
            mock_temp_instance.name = "/tmp/test.pdf"
            mock_temp.return_value = mock_temp_instance
            
            with pytest.raises(HTTPException) as exc_info:
                await upload_pdf(mock_file, mock_background)
            
            assert exc_info.value.status_code == 400
            assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_size_limit_error(self):
        """Test temp file is cleaned up when file exceeds size limit."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        
        from src.core.constants import MAX_FILE_SIZE
        
        # First read header, then large chunk that exceeds limit
        mock_file.file.read.side_effect = [
            b"%PDF-",
            b"x" * (MAX_FILE_SIZE + 1),
        ]
        
        with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp_instance = MagicMock()
            mock_temp_instance.name = "/tmp/test.pdf"
            mock_temp.return_value = mock_temp_instance
            
            with patch('src.routers.pdf_tasks.os.path.exists', return_value=True):
                with patch('src.routers.pdf_tasks.os.remove') as mock_remove:
                    with pytest.raises(HTTPException):
                        await upload_pdf(mock_file, mock_background)
                    
                    # Temp file should be closed and removed
                    mock_temp_instance.close.assert_called()
                    mock_remove.assert_called_with("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_general_exception(self):
        """Test temp file is cleaned up on general exception after tmp_path is set."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        
        # Simulate successful header and content read
        # Exception happens during flush/close operations
        mock_file.file.read.side_effect = [
            b"%PDF-",  # Header
            b"content",  # Content
            b"",  # EOF
        ]
        
        with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp_instance = MagicMock()
            mock_temp_instance.name = "/tmp/test.pdf"
            # flush() succeeds but close() fails
            mock_temp_instance.flush.return_value = None
            mock_temp_instance.close.side_effect = Exception("Close failed")
            mock_temp.return_value = mock_temp_instance
            
            with patch('src.routers.pdf_tasks.os.path.exists', return_value=True):
                with patch('src.routers.pdf_tasks.os.remove') as mock_remove:
                    with pytest.raises(HTTPException) as exc_info:
                        await upload_pdf(mock_file, mock_background)
                    
                    assert exc_info.value.status_code == 500
                    
                    # Temp file close was attempted and failed
                    mock_temp_instance.close.assert_called()

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_create_analysis_failure(self):
        """Test temp file is cleaned up when create_analysis fails."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file with valid PDF header
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        mock_file.file.read.side_effect = [
            b"%PDF-",
            b" content",
            b"",
        ]
        
        with patch('src.routers.pdf_tasks.create_analysis', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.name = "/tmp/test.pdf"
                mock_temp.return_value = mock_temp_instance
                
                with patch('src.routers.pdf_tasks.os.path.exists', return_value=True):
                    with patch('src.routers.pdf_tasks.os.remove') as mock_remove:
                        with pytest.raises(HTTPException) as exc_info:
                            await upload_pdf(mock_file, mock_background)
                        
                        assert exc_info.value.status_code == 500
                        
                        # Temp file should be closed and removed
                        mock_temp_instance.close.assert_called()
                        mock_remove.assert_called_with("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_remove_fails_during_cleanup(self):
        """Test failed remove during cleanup is suppressed."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        
        from src.core.constants import MAX_FILE_SIZE
        
        mock_file.file.read.side_effect = [
            b"%PDF-",
            b"x" * (MAX_FILE_SIZE + 1),
        ]
        
        with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp_instance = MagicMock()
            mock_temp_instance.name = "/tmp/test.pdf"
            mock_temp.return_value = mock_temp_instance
            
            with patch('src.routers.pdf_tasks.os.path.exists', return_value=True):
                with patch('src.routers.pdf_tasks.os.remove') as mock_remove:
                    mock_remove.side_effect = Exception("Remove failed")
                    
                    with pytest.raises(HTTPException):
                        await upload_pdf(mock_file, mock_background)
                    
                    # Should have attempted to remove
                    mock_remove.assert_called_with("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_create_analysis_fails(self):
        """Test handling when create_analysis fails."""
        mock_background = MagicMock(spec=BackgroundTasks)
        
        # Create a mock file with valid PDF header
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.file = MagicMock()
        mock_file.file.read.side_effect = [
            b"%PDF-",
            b" content",
            b"",
        ]
        
        with patch('src.routers.pdf_tasks.create_analysis', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            with patch('src.routers.pdf_tasks.tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.name = "/tmp/test.pdf"
                mock_temp.return_value = mock_temp_instance
                
                with pytest.raises(HTTPException) as exc_info:
                    await upload_pdf(mock_file, mock_background)
                
                assert exc_info.value.status_code == 500
                assert "analysis record" in exc_info.value.detail.lower()


class TestGetResult:
    """Tests for get_result endpoint."""

    @pytest.mark.asyncio
    async def test_task_not_found(self):
        """Test 404 when task doesn't exist."""
        with patch('src.routers.pdf_tasks.get_analysis', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_result("non-existent-id")
            
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Task not found"

    @pytest.mark.asyncio
    async def test_task_found_basic(self):
        """Test getting task result with basic status."""
        mock_analysis = MagicMock()
        mock_analysis.status = "completed"
        mock_analysis.result = None
        
        with patch('src.routers.pdf_tasks.get_analysis', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_analysis
            
            result = await get_result("test-task-id")
            
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_task_found_with_dict_result(self):
        """Test getting task result with dict result."""
        mock_analysis = MagicMock()
        mock_analysis.status = "completed"
        mock_analysis.result = {
            "score": 85,
            "ratio_liquidity": 1.5,
        }
        
        with patch('src.routers.pdf_tasks.get_analysis', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_analysis
            
            result = await get_result("test-task-id")
            
            assert result["status"] == "completed"
            assert result["score"] == 85
            assert result["ratio_liquidity"] == 1.5

    @pytest.mark.asyncio
    async def test_task_found_with_non_dict_result(self):
        """Test getting task result with non-dict result."""
        mock_analysis = MagicMock()
        mock_analysis.status = "processing"
        mock_analysis.result = "some string result"
        
        with patch('src.routers.pdf_tasks.get_analysis', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_analysis
            
            result = await get_result("test-task-id")
            
            assert result["status"] == "processing"
            # Non-dict results should not be merged into payload
            assert "result" not in result or result.get("result") != "some string result"

    @pytest.mark.asyncio
    async def test_db_failure_raises_database_error(self):
        """DB lookup failures should become explicit DatabaseError instances."""
        with patch(
            "src.routers.pdf_tasks.get_analysis",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("db down"),
        ):
            with pytest.raises(DatabaseError):
                await get_result("broken-task-id")
