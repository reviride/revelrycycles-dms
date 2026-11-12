# Copyright (c) 2026, Revelry Cycles
# License: GPLv3

from base64 import b64encode
from io import BytesIO


def job_qr(text):
	"""Data URI of a QR code for the job number, for the printed job card (scan to open the job)."""
	from pyqrcode import create

	stream = BytesIO()
	create(str(text)).svg(stream, scale=3, background="#fff", module_color="#000", xmldecl=False, svgns=True)
	return "data:image/svg+xml;base64," + b64encode(stream.getvalue()).decode()
