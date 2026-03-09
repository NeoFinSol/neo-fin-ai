import io
import json
from typing import BinaryIO

import pdfplumber

from src.core import prompts
from src.core.agent import agent
from src.exceptions.PdfExtractException import PdfExtractException


def _read_pdf_file(file: io.BytesIO | BinaryIO) -> list[dict]:
	file_data = []

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
		file_content = _read_pdf_file(file)
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

		res = (await agent.request("84bd75e8-0796-4066-a278-fb566b0cb8be", prompt,
							system=prompts.PDF_EXTRACT_METRICS))["content"]
		if res is not None:
			with open("out.txt", "a", encoding="utf-8") as f:
				f.write(res)
