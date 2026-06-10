from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import random
import numpy as np
import barcode
from barcode.writer import ImageWriter
import io


def _add_noise(img: Image.Image, intensity: int = 6) -> Image.Image:
    arr = np.array(img).astype('int16')
    noise = np.random.randint(-intensity, intensity, arr.shape, dtype='int16')
    arr = np.clip(arr + noise, 0, 255).astype('uint8')
    return Image.fromarray(arr)


def _draw_security_pattern(draw, width, height, color=(180, 170, 200, 40)):
    for i in range(0, width, 30):
        for j in range(0, height, 30):
            r = random.randint(8, 18)
            draw.ellipse([(i, j), (i+r, j+r)], outline=color, width=1)


def generate_cin_recto(profile: dict, output_dir: str = "output/cin") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{output_dir}/cin_recto_{profile['cin']}.png"

    width, height = 1012, 638
    img = Image.new("RGBA", (width, height), (245, 242, 250, 255))
    pattern_layer = Image.new("RGBA", (width, height), (0,0,0,0))
    pattern_draw = ImageDraw.Draw(pattern_layer)
    _draw_security_pattern(pattern_draw, width, height)
    img = Image.alpha_composite(img, pattern_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Bordure carte
    draw.rectangle([(2, 2), (width-3, height-3)],
                   outline=(140, 120, 180), width=3)

    # Bande violette verticale droite
    draw.rectangle([(width-180, 0), (width, height)],
                   fill=(180, 160, 210))

    # Drapeau tunisien (simulation) - carre rouge avec croissant
    flag_x, flag_y = width-160, 30
    draw.rectangle([(flag_x, flag_y), (flag_x+100, flag_y+70)],
                   fill=(220, 30, 50))
    draw.ellipse([(flag_x+25, flag_y+10), (flag_x+75, flag_y+60)],
                 fill="white")
    draw.ellipse([(flag_x+32, flag_y+15), (flag_x+72, flag_y+55)],
                 fill=(220, 30, 50))
    draw.text((flag_x+38, flag_y+28), "*", fill="white")

    # Texte arabe header (simule)
    draw.text((width-175, 115), "bطاقة التعريف", fill=(80, 40, 120))
    draw.text((width-175, 140), "الوطني", fill=(80, 40, 120))

    # Photo placeholder (noir et blanc)
    photo_x, photo_y = 40, 60
    draw.rectangle([(photo_x, photo_y), (photo_x+160, photo_y+200)],
                   fill=(200, 200, 200), outline=(120, 120, 120), width=2)
    draw.text((photo_x+45, photo_y+90), "PHOTO", fill=(100, 100, 100))

    # Infos en arabe (simulees avec latin pour lisibilite OCR)
    draw.text((230, 70),  f"الاسم : {profile['nom'].upper()}", fill=(40, 40, 40))
    draw.text((230, 110), f"اللقب : {profile['prenom'].upper()}", fill=(40, 40, 40))
    draw.text((230, 150), f"تاريخ الولادة : {profile['date_naissance']}", fill=(40, 40, 40))
    draw.text((230, 190), f"مكان الولادة : {profile['adresse'].upper()}", fill=(40, 40, 40))

    # Numero CIN
    draw.rectangle([(40, 290), (400, 340)], fill=(80, 40, 120))
    draw.text((55, 300), f"CIN : {profile['cin']}", fill="white")

    # Date expiration
    draw.text((230, 360), "تاريخ الانتهاء : 31/12/2029", fill=(80, 40, 120))

    # MRZ bas de carte
    draw.rectangle([(0, height-70), (width, height)], fill=(235, 232, 245))
    mrz1 = f"IDTUN{profile['cin']}<<<<<<<<<<<<<<<<<<<<"
    mrz2 = f"{profile['nom'].upper().replace(' ','<')}<<{profile['prenom'].upper()}<<<<<<<<<<<"
    draw.text((20, height-65), mrz1[:60], fill=(60, 60, 60))
    draw.text((20, height-45), mrz2[:60], fill=(60, 60, 60))

    img = _add_noise(img)
    img.save(filename, "PNG")
    return filename


def generate_cin_verso(profile: dict, output_dir: str = "output/cin") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename_png = f"{output_dir}/cin_verso_{profile['cin']}.png"

    width, height = 1012, 638
    img = Image.new("RGBA", (width, height), (245, 242, 250, 255))
    pattern_layer = Image.new("RGBA", (width, height), (0,0,0,0))
    pattern_draw = ImageDraw.Draw(pattern_layer)
    _draw_security_pattern(pattern_draw, width, height)
    img = Image.alpha_composite(img, pattern_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    draw.rectangle([(2, 2), (width-3, height-3)],
                   outline=(140, 120, 180), width=3)

    # Bande code barre gauche
    try:
        import barcode
        from barcode.writer import ImageWriter
        code128 = barcode.get('code128', profile['cin'], writer=ImageWriter())
        buf = io.BytesIO()
        code128.write(buf, options={
            "module_height": 25.0,
            "module_width": 0.8,
            "quiet_zone": 2.0,
            "text_distance": 3.0,
            "font_size": 8,
            "write_text": True,
        })
        buf.seek(0)
        barcode_img = Image.open(buf).convert("RGB")
        barcode_img = barcode_img.resize((90, 320))
        # Rotation verticale
        barcode_img = barcode_img.rotate(90, expand=True)
        img.paste(barcode_img, (10, 150))
    except Exception:
        draw.rectangle([(10, 150), (100, 470)], fill=(220, 220, 220))
        draw.text((20, 300), profile['cin'], fill=(60,60,60))

    # Infos verso en arabe
    draw.text((130, 60),  f"العنوان : {profile['adresse']}", fill=(40, 40, 40))
    draw.text((130, 100), f"المهنة : {profile['poste']}", fill=(40, 40, 40))
    draw.text((130, 140), f"صاحب العمل : {profile['employeur']}", fill=(40, 40, 40))
    draw.text((130, 180), f"سنة الاصدار : 2022", fill=(40, 40, 40))
    draw.text((130, 220), f"تاريخ الانتهاء : 31/12/2029", fill=(80, 40, 120))

    # Cachet officiel (tampon bleu simule)
    draw.ellipse([(350, 350), (530, 530)],
                 outline=(60, 80, 160), width=3)
    draw.ellipse([(370, 370), (510, 510)],
                 outline=(60, 80, 160), width=2)
    draw.text((390, 425), "REPUBLIQUE", fill=(60, 80, 160))
    draw.text((395, 445), "TUNISIENNE", fill=(60, 80, 160))

    # Empreinte digitale simulee
    fp_x, fp_y = 600, 370
    draw.ellipse([(fp_x, fp_y), (fp_x+120, fp_y+150)],
                 fill=(200, 195, 210), outline=(150, 145, 165), width=1)
    for i in range(8):
        r = 15 + i * 7
        draw.ellipse([(fp_x+60-r, fp_y+75-r), (fp_x+60+r, fp_y+75+r)],
                     outline=(140, 130, 150), width=1)
    draw.text((fp_x+10, fp_y+160), "EMPREINTE", fill=(100, 100, 120))

    img = _add_noise(img)
    img.save(filename_png, "PNG")
    return filename_png


def generate_cin(profile: dict, output_dir: str = "output/cin") -> dict:
    recto = generate_cin_recto(profile, output_dir)
    verso = generate_cin_verso(profile, output_dir)
    return {"recto": recto, "verso": verso}


if __name__ == "__main__":
    import json
    with open("output/profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    for p in profiles:
        paths = generate_cin(p)
        print(f"Genere : {paths['recto']} | {paths['verso']}")
    print("Toutes les CIN sont generees.")
