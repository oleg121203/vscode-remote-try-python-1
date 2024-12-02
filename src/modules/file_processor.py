# modules/file_processor.py

import re
from typing import List
import os

# Імпорт необхідних бібліотек для роботи з різними форматами файлів
import PyPDF2
from docx import Document
import pandas as pd
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

class FileProcessor:
    TELEGRAM_LINK_PATTERN = r'(https?://t\.me/[\w_+/]+)'

    def __init__(self):
        pass

    def extract_links_from_file(self, file_path: str) -> List[str]:
        """Визначає тип файлу та витягує посилання на Telegram."""
        file_extension = os.path.splitext(file_path)[1].lower()
        links = []

        if file_extension == '.pdf':
            links = self.extract_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            links = self.extract_from_word(file_path)
        elif file_extension in ['.xlsx', '.xls', '.csv']:
            links = self.extract_from_excel(file_path)
        elif file_extension == '.txt':
            links = self.extract_from_txt(file_path)
        elif file_extension == '.html':
            links = self.extract_from_html(file_path)
        elif file_extension == '.xml':
            links = self.extract_from_xml(file_path)
        else:
            # Спробуємо відкрити як текстовий файл
            links = self.extract_from_txt(file_path)

        return links

    def extract_from_pdf(self, file_path: str) -> List[str]:
        links = []
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    page_links = re.findall(self.TELEGRAM_LINK_PATTERN, text)
                    links.extend(page_links)
        except Exception as e:
            print(f"Error extracting from PDF: {e}")
        return links

    def extract_from_word(self, file_path: str) -> List[str]:
        links = []
        try:
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            text = '\n'.join(full_text)
            links = re.findall(self.TELEGRAM_LINK_PATTERN, text)
        except Exception as e:
            print(f"Error extracting from Word: {e}")
        return links

    def extract_from_excel(self, file_path: str) -> List[str]:
        links = []
        try:
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, dtype=str)
            else:
                xls = pd.ExcelFile(file_path)
                df = pd.concat([pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names])
            for col in df.columns:
                col_data = df[col].dropna().astype(str)
                for cell in col_data:
                    cell_links = re.findall(self.TELEGRAM_LINK_PATTERN, cell)
                    links.extend(cell_links)
        except Exception as e:
            print(f"Error extracting from Excel/CSV: {e}")
        return links

    def extract_from_txt(self, file_path: str) -> List[str]:
        links = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                links = re.findall(self.TELEGRAM_LINK_PATTERN, text)
        except Exception as e:
            print(f"Error extracting from TXT: {e}")
        return links

    def extract_from_html(self, file_path: str) -> List[str]:
        links = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                text = soup.get_text()
                links = re.findall(self.TELEGRAM_LINK_PATTERN, text)
        except Exception as e:
            print(f"Error extracting from HTML: {e}")
        return links

    def extract_from_xml(self, file_path: str) -> List[str]:
        links = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            text = ET.tostring(root, encoding='utf-8', method='text').decode('utf-8')
            links = re.findall(self.TELEGRAM_LINK_PATTERN, text)
        except Exception as e:
            print(f"Error extracting from XML: {e}")
        return links

    # Додайте інші методи для підтримки інших форматів за потреби