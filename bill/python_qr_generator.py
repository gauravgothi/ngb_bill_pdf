import qrcode
from qrcode.image.pil import PilImage

# The URL provided by the user
URL_TO_ENCODE = "https://wa.me/917312426395"
# The name of the output file
OUTPUT_FILENAME = "whatsapp_qr_link.png"

# --- 1. Create the QR code generator instance ---
# box_size: Controls the size of the box (pixels) for each 'tile' of the QR code.
# border: Controls how many boxes thick the border around the code is (minimum is 4).
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L, # Error correction level L (about 7% or less errors can be corrected)
    box_size=10,
    border=1,
)

# --- 2. Add the data (the URL) ---
qr.add_data(URL_TO_ENCODE)
qr.make(fit=True)

# --- 3. Create the image and save it ---
# The 'image_factory=PilImage' ensures the output is a Pillow image object
img = qr.make_image(fill_color="black", back_color="white", image_factory=PilImage)

# Save the image file
try:
    img.save(OUTPUT_FILENAME)
    print(f"✅ Successfully generated QR code for: {URL_TO_ENCODE}")
    print(f"File saved as: {OUTPUT_FILENAME}")
except Exception as e:
    print(f"❌ An error occurred while saving the file: {e}")

# The generated file will look something like this:
# [Image of the generated QR code image]