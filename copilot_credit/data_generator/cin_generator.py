import os
import random
import math
import shutil
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
import barcode as barcode_lib
from barcode.writer import ImageWriter
import io
from pathlib import Path

WIDTH = 1012
HEIGHT = 638
FONT_PATH = "assets/Cairo-Regular.ttf"

def ar(text):
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

def create_background():
    img = Image.new("RGB", (WIDTH, HEIGHT), (245, 240, 250))
    draw = ImageDraw.Draw(img)
    for _ in range(80):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        r = random.randint(8, 24)
        color = (255, 190, 220)
        draw.ellipse((x-r, y-r, x+r, y+r), outline=color)
        for angle in range(0, 360, 45):
            px = x + int(r * math.cos(math.radians(angle)))
            py = y + int(r * math.sin(math.radians(angle)))
            draw.line((x, y, px, py), fill=color, width=1)
    return img

def add_noise(img):
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, 7, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    return img

def random_rotate(img):
    angle = random.uniform(-1, 1)
    return img.rotate(angle, expand=False, fillcolor=(245, 240, 250))

def fake_photo():
    img = Image.new("L", (210, 260), 210)
    draw = ImageDraw.Draw(img)
    draw.ellipse((60, 20, 150, 120), fill=150)
    draw.rectangle((80, 120, 130, 150), fill=150)
    draw.polygon([(50, 240), (160, 240), (130, 150), (80, 150)], fill=130)
    return img.convert("RGB")

def make_fingerprint():
    img = Image.new("RGB", (180, 180), "white")
    draw = ImageDraw.Draw(img)
    center = (90, 90)
    for r in range(10, 80, 8):
        bbox = (center[0]-r, center[1]-r, center[0]+r, center[1]+r)
        draw.arc(bbox, 20, 340, fill="black", width=2)
    return img

def make_barcode_img(cin_num):
    try:
        code128 = barcode_lib.get('code128', cin_num, writer=ImageWriter())
        buf = io.BytesIO()
        code128.write(buf, options={
            "module_height": 15.0,
            "module_width": 0.7,
            "quiet_zone": 1.0,
            "write_text": False,
        })
        buf.seek(0)
        bc_img = Image.open(buf).convert("RGB")
        bc_img = bc_img.resize((55, 360))
        bc_img = bc_img.rotate(90, expand=True)
        return bc_img
    except:
        img = Image.new("RGB", (360, 55), "white")
        draw = ImageDraw.Draw(img)
        x = 5
        while x < 355:
            w = random.randint(1, 4)
            draw.rectangle((x, 0, x+w, 55), fill="black")
            x += w + random.randint(1, 3)
        return img

def draw_tunisian_flag(draw, x, y, w=120, h=80):
    draw.rectangle((x, y, x+w, y+h), fill=(220, 0, 0))
    cx, cy = x + w//2, y + h//2
    r = int(h * 0.32)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline="white", width=4)
    draw.ellipse((cx-r+6, cy-r+2, cx+r+2, cy+r-2), fill=(220,0,0))
    draw.text((cx-8, cy-10), "*", fill="white",
              font=ImageFont.truetype(FONT_PATH, 18))

def generate_cin_recto(profile, output_dir="output/cin"):
    os.makedirs(output_dir, exist_ok=True)
    img = create_background()
    draw = ImageDraw.Draw(img)

    purple = (110, 50, 180)
    blue   = (20, 70, 180)
    gold   = (180, 140, 10)

    f36 = load_font(36)
    f34 = load_font(34)
    f28 = load_font(28)
    f22 = load_font(22)
    f18 = load_font(18)
    f14 = load_font(14)

    # Photo
    photo = fake_photo()
    img.paste(photo, (35, 50))

    # Drapeau
    draw_tunisian_flag(draw, 830, 35, w=120, h=80)

    # Titre arabe
    draw.text((420, 30),  ar("الجمهورية التونسية"), font=f28, fill=purple)
    draw.text((380, 75),  ar("بطاقة التعريف الوطنية"), font=f28, fill=purple)

    # Infos personnelles
    draw.text((270, 120), ar("الاسم العائلي :"), font=f22, fill=purple)
    draw.text((270, 155), profile["nom"].upper(), font=f28, fill=blue)

    draw.text((270, 200), ar("الاسم الشخصي :"), font=f22, fill=purple)
    draw.text((270, 235), profile["prenom"].upper(), font=f28, fill=blue)

    draw.text((270, 280), ar("تاريخ الولادة :"), font=f22, fill=purple)
    draw.text((500, 280), profile["date_naissance"], font=f22, fill=blue)

    draw.text((270, 320), ar("مكان الولادة :"), font=f22, fill=purple)
    draw.text((500, 320), profile["adresse"].upper(), font=f22, fill=blue)

    # CIN band
    draw.rounded_rectangle((260, 365, 800, 420),
                            radius=8, fill=(180, 140, 220))
    draw.text((285, 372), profile["cin"], font=f34, fill="white")

    draw.text((260, 428), ar("رقم بطاقة التعريف الوطنية"),
              font=f18, fill=purple)

    # Dates bas
    draw.text((35, HEIGHT-100),
              f"Lieu de naissance : {profile['adresse']}",
              font=f14, fill=(80,65,105))
    draw.text((35, HEIGHT-78),
              "Date d'emission : 15/03/2022",
              font=f14, fill=(80,65,105))
    draw.text((35, HEIGHT-56),
              "Date d'expiration : 31/12/2029",
              font=f14, fill=(80,65,105))

    # Cachet dore
    for r, w in [(55,3),(45,2),(35,1)]:
        draw.ellipse((WIDTH-130-r, HEIGHT-130-r,
                      WIDTH-130+r, HEIGHT-130+r),
                     outline=gold, width=w)
    draw.text((WIDTH-175, HEIGHT-140),
              "REPUBLIQUE", font=f14, fill=gold)
    draw.text((WIDTH-172, HEIGHT-122),
              "TUNISIENNE", font=f14, fill=gold)

    # MRZ
    draw.rectangle((0, HEIGHT-34, WIDTH, HEIGHT),
                   fill=(232, 226, 245))
    mrz = f"IDTUN{profile['cin']}<<{profile['nom'].upper()}<<{profile['prenom'].upper()}"
    draw.text((12, HEIGHT-28), mrz[:65], font=f14, fill=(50,40,75))

    img = add_noise(img)
    img = random_rotate(img)
    path = os.path.join(output_dir, f"cin_recto_{profile['cin']}.png")
    img.save(path, dpi=(300, 300))
    return path


def generate_cin_verso(profile, output_dir="output/cin"):
    os.makedirs(output_dir, exist_ok=True)
    img = create_background()
    draw = ImageDraw.Draw(img)

    purple = (110, 50, 180)
    blue   = (20, 70, 180)

    f28 = load_font(28)
    f22 = load_font(22)
    f18 = load_font(18)
    f14 = load_font(14)

    # 02 + rh haut gauche
    draw.text((18, 18), "02", font=f22, fill=purple)
    draw.text((18, 48), "rh", font=f14, fill=(100,88,118))

    # Annee haut droite
    draw.text((WIDTH-100, 18), "2022", font=f22, fill=(30,25,90))

    # Code barre vertical - bord gauche
    bc = make_barcode_img(profile['cin'])
    bc = bc.resize((42, HEIGHT - 60))
    img.paste(bc, (4, 30))

    # Ligne separatrice
    draw.line([(52, 20), (52, HEIGHT-20)],
              fill=(180,155,200), width=1)

    # 02 + rh repositionnes apres la ligne
    draw.text((62, 18), "02", font=f22, fill=purple)
    draw.text((62, 48), "rh", font=f14, fill=(100,88,118))

    x = 75
    draw.text((x, 50),  ar(f"الاسم العائلي : {profile['nom'].upper()}"),
              font=f22, fill=blue)
    draw.text((x, 95),  ar(f"الاسم الشخصي : {profile['prenom'].upper()}"),
              font=f22, fill=blue)
    draw.text((x, 140), ar(f"تاريخ الولادة : {profile['date_naissance']}"),
              font=f22, fill=blue)
    draw.text((x, 185), ar(f"مكان الولادة : {profile['adresse'].upper()}"),
              font=f22, fill=blue)
    draw.text((x, 230), ar(f"المهنة : {profile['poste']}"),
              font=f22, fill=blue)
    draw.text((x, 275), ar("تاريخ الانتهاء : 31/12/2029"),
              font=f18, fill=purple)

    # Tampon bleu
    sx, sy = 160, 390
    for r, w in [(90,3),(78,2),(65,1)]:
        draw.ellipse((sx-r, sy-r, sx+r, sy+r),
                     outline=(40,80,200), width=w)
    draw.text((sx-62, sy-30), "REPUBLIQUE",  font=f14, fill=(40,80,200))
    draw.text((sx-58, sy-10), "TUNISIENNE",  font=f14, fill=(40,80,200))
    draw.text((sx-52, sy+8),  "MINISTERE",   font=f14, fill=(40,80,200))
    draw.text((sx-50, sy+26), "INTERIEUR",   font=f14, fill=(40,80,200))

    # Empreinte
    fp = make_fingerprint()
    img.paste(fp, (420, 320))
    draw.text((438, 508), "Empreinte digitale",
              font=f14, fill=(90,80,110))

    # Texte arabe bas droite
    draw.text((620, 400), ar("الجمهورية التونسية"),
              font=f18, fill=purple)
    draw.text((620, 435), ar("وزارة الداخلية"),
              font=f18, fill=purple)

    img = add_noise(img)
    img = random_rotate(img)
    path = os.path.join(output_dir, f"cin_verso_{profile['cin']}.png")
    img.save(path, dpi=(300, 300))
    return path


def generate_cin(profile, output_dir="output/cin"):
    recto = generate_cin_recto(profile, output_dir)
    verso  = generate_cin_verso(profile, output_dir)
    return {"recto": recto, "verso": verso}


if __name__ == "__main__":
    import json
    cin_dir = Path("output/cin")
    if cin_dir.exists():
        shutil.rmtree(cin_dir)
    cin_dir.mkdir(parents=True)

    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    for p in profiles:
        paths = generate_cin(p)
        print(f"OK : {paths['recto'].split(chr(92))[-1]}")
    print(f"\n{len(profiles)*2} images generees.")