import asyncio
import io
import json
from typing import BinaryIO
import os

import pdfplumber
from fastapi import HTTPException

from src.core import prompts
from src.core.agent import agent
from src.exceptions.PdfExtractException import PdfExtractException


def _read_pdf_file(file: io.BytesIO) -> list[dict]:
	file_data = []

	# Reset file pointer to beginning
	file.seek(0)
	
	with pdfplumber.open(file) as pdf:
		for page_num, page in enumerate(pdf.pages, start=1):
			tables = page.extract_tables(table_settings={
				"vertical_strategy": "lines",
				"horizontal_strategy": "lines",
				"min_words_vertical": 3,
				"snap_tolerance": 3
			})

			page_data = {
				"page": page_num,
				# "text": page.extract_text(),
				"tables": []
			}

			for table_idx, table in enumerate(tables):
				if not table:
					continue

				cleaned_rows = [
					[cell.strip() if cell else "" for cell in row]
					for row in table
				]

				page_data["tables"].append({
					"table_index": table_idx,
					"rows": cleaned_rows
				})

			file_data.append(page_data)

	return file_data


async def analyze_pdf(file: io.BytesIO | BinaryIO):
	try:
		# Convert BinaryIO to BytesIO if needed
		if isinstance(file, io.BytesIO):
			pdf_file = file
		else:
			# For BinaryIO, we need to read the content and create BytesIO
			content = file.read()
			if not content:
				raise ValueError("Empty file content")
			pdf_file = io.BytesIO(content)

		file_content = _read_pdf_file(pdf_file)
	except Exception as e:
		# Return proper FastAPI HTTP Exception instead of custom exception
		raise HTTPException(status_code=400, detail=f"PDF processing failed: {str(e)}")

	print("Request to AI")

	# Iterate pages by step and prepare for AI
	step = 20
	all_results = []
	for page_idx in range(0, len(file_content), step):
		end_idx = min(page_idx + step, len(file_content))
		print(f"Pages {page_idx + 1} - {end_idx}")

		prompt = ""
		for i in range(page_idx, end_idx):
			prompt += f"=== PAGE {i + 1} ===\n"
			prompt += json.dumps(file_content[i]) + "\n"

		# Call the AI agent with the prepared prompt
		try:
			res = await agent.invoke(
				input={
					"tool_input": prompt,
					"intermediate_steps": []
				}
			)
			if res is not None:
				with open("out.txt", "a", encoding="utf-8") as f:
					f.write(res)
				all_results.append(json.loads(res))
		except asyncio.TimeoutError:
			raise HTTPException(status_code=504, detail="AI request timeout")
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

	# Combine results from all pages
	if all_results:
		return all_results[0] if len(all_results) == 1 else {"pages": all_results}
	return {}
