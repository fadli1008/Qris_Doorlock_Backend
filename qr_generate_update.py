import qrcode
import json
from PIL import Image, ImageDraw, ImageFont

# Data transaksi yang ingin dimasukkan ke QR
data = {
    "uid": "DOORLOCK001",
    "amount": 20000
}

# Konversi ke format JSON
json_data = json.dumps(data)

# Generate QR code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)
qr.add_data(json_data)
qr.make(fit=True)

# Buat gambar dari QR code
img = qr.make_image(fill_color="black", back_color="white")

# Konversi ke mode RGB agar bisa ditambahkan teks
img = img.convert("RGB")

# Buat objek untuk menggambar
draw = ImageDraw.Draw(img)

# Tentukan font (gunakan font default atau spesifik jika tersedia)
try:
    font = ImageFont.truetype("arial.ttf", 20)  # Ganti dengan path font jika perlu
except:
    font = ImageFont.load_default()

# Teks yang akan ditambahkan
label_text = f"UID: {data['uid']}\nAmount: {data['amount']}"

# Hitung ukuran teks untuk menentukan posisi
text_bbox = draw.textbbox((0, 0), label_text, font=font)
text_width = text_bbox[2] - text_bbox[0]
text_height = text_bbox[3] - text_bbox[1]

# Ukuran gambar QR
img_width, img_height = img.size

# Tambahkan padding di bawah QR untuk teks
new_height = img_height + text_height + 20  # Tambah ruang untuk teks
new_img = Image.new("RGB", (img_width, new_height), "white")
new_img.paste(img, (0, 0))

# Buat ulang objek draw untuk gambar baru
draw = ImageDraw.Draw(new_img)

# Posisi teks di tengah bawah
text_x = (img_width - text_width) // 2
text_y = img_height + 10  # Sedikit padding dari QR

# Tambahkan teks ke gambar
draw.text((text_x, text_y), label_text, font=font, fill="black")

# Simpan QR code dengan label ke file
new_img.save("qr_transaksi_with_label.png")

print("✅ QR code dengan label berhasil dibuat dan disimpan sebagai qr_transaksi_with_label.png")