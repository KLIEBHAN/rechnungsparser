import os
import sys
from invoice2data import extract_data
from invoice2data.extract.loader import read_templates
import tkinter as tk
from tkinter import messagebox
import PyPDF2
import re
from datetime import datetime

def extract_text_from_pdf(pdf_path):
    pdf_file = open(pdf_path, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    num_pages = len(pdf_reader.pages)

    text = ''
    for page in range(num_pages):
        text += pdf_reader.pages[page].extract_text()

    pdf_file.close()
    return text

def extract_invoice_data(pdf_path):
    templates = read_templates('templates')
    invoice_data = extract_data(pdf_path, templates=templates)

    return invoice_data

def show_popup(message, title='Rechnungsdaten'):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(title, message)
    root.destroy()

if __name__ == '__main__':

    if len(sys.argv) != 2:
        print("Usage: python main.py /path/to/invoice.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print("Error: The specified PDF file does not exist.")
        sys.exit(1)

    pdftext = extract_text_from_pdf(pdf_path)
    invoice_data = extract_invoice_data(pdf_path)
    
    if invoice_data:
        invoice_date = invoice_data['date']
        invoice_number = invoice_data['invoice_number']
        formatted_date = invoice_date.strftime('%d.%m.%Y')
        message = f"Rechnungsdatum: {formatted_date}\nRechnungsnummer: {invoice_number}"
        show_popup(message)
    else:
        show_popup("Rechnungsdaten nicht gefunden.")
