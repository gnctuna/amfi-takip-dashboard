import urllib.request
import os
import zipfile
import shutil

# Klasör yoksa oluştur
if not os.path.exists("models"):
    os.makedirs("models")

MODEL_URL = "https://storage.googleapis.com/download.tensorflow.org/models/tflite/coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.zip"
ZIP_PATH = "models/model.zip"

print("1. Model indiriliyor...")
urllib.request.urlretrieve(MODEL_URL, ZIP_PATH)

print("2. Zip açılıyor...")
with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
    zip_ref.extractall("models")

print("3. Dosyalar yerleştiriliyor...")

# Dosyaları ismine göre arayıp buluyoruz (Klasör adı ne olursa olsun)
found_tflite = False
found_label = False

for root, dirs, files in os.walk("models"):
    for file in files:
        if file == "detect.tflite":
            # Dosyayı bulduk, ana klasöre taşıyalım
            source = os.path.join(root, file)
            shutil.move(source, "models/detect.tflite")
            found_tflite = True
            print("   -> detect.tflite bulundu ve taşındı.")
            
        elif "labelmap" in file and file.endswith(".txt"):
            # Etiket dosyasını bulduk
            source = os.path.join(root, file)
            shutil.move(source, "models/labelmap.txt")
            found_label = True
            print("   -> labelmap.txt bulundu ve taşındı.")

# Temizlik (Zip dosyasını ve artık klasörleri sil)
if os.path.exists(ZIP_PATH):
    os.remove(ZIP_PATH)

# Eski klasörleri temizle (Sadece dosyalar kalsın)
for root, dirs, files in os.walk("models", topdown=False):
    for name in dirs:
        try:
            os.rmdir(os.path.join(root, name))
        except:
            pass # Klasör boş değilse silme, önemli değil

if found_tflite and found_label:
    print("\n✅ BAŞARILI! Model dosyaları hazır.")
else:
    print("\n❌ HATA: Dosyalar zip içinden çıkmadı.")