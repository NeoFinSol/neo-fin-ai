import io
import json
from typing import BinaryIO
import os

import pdfplumber

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
			pdf_file = io.BytesIO(content)
		
		file_content = _read_pdf_file(pdf_file)
	except Exception as e:
		raise PdfExtractException(detail=str(e))

	print("Request to AI")

	# Iterate pages by step and prepare for AI
	step = 20
	for page_idx in range(0, 20, step):
		print(f"Pages {page_idx + 1} - {page_idx + step + 1}")

		prompt = ""
		for i in range(0, step):
			if page_idx + i >= len(file_content):
				continue

			prompt += f"=== PAGE {page_idx + i + 1} ===\n"
			prompt += json.dumps(file_content[page_idx + i]) + "\n"

		# Call the AI agent with the prepared prompt
		res = await agent.invoke(
			input={
				"tool_input": prompt,
				"intermediate_steps": []
			}
		)
		if res is not None:
			with open("out.txt", "a", encoding="utf-8") as f:
				f.write(res)
		return json.loads(res)
