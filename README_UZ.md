# Musiqa Bot — o‘rnatish qo‘llanmasi

## Nimalar bor?
- Qo‘shiq nomi yozilsa, Jamendo katalogidan 10 ta natija chiqaradi.
- Natija tanlanganda, provayder yuklab olishga ruxsat bergan trekni MP3 qilib yuboradi; aks holda havola beradi.
- Ovozli xabarda aytilgan qo‘shiq nomini `OPENAI_API_KEY` orqali matnga aylantirib qidiradi.
- Video/audio faylni `AUDD_TOKEN` orqali tanishga urinadi va aniqlangan nom bo‘yicha 10 ta trek qidiradi.
- Botda so‘nggi 30 kunda faol bo‘lgan foydalanuvchilar soni ko‘rsatiladi. Bu haqiqiy hisob, sun’iy raqam emas.

## Muhim
Bot mualliflik huquqini chetlab o‘tib tijoriy qo‘shiqlarni ruxsatsiz yuklab bermaydi. Yuklab olish faqat katalog ruxsat bergan treklar uchun ishlaydi. AudD va OpenAI kabi xizmatlar uchun alohida API kalitlari va tariflari bo‘lishi mumkin.

## 1. Kerakli akkauntlar
1. Telegram’da `@BotFather` ga yozib `/newbot` qiling va token oling.
2. Jamendo Developer portalidan Client ID oling: https://developer.jamendo.com/
3. Video/audio orqali tanish uchun AudD token oling: https://audd.io/
4. Ovozli xabarda aytilgan so‘zni matnga aylantirish uchun OpenAI API key oling: https://platform.openai.com/api-keys

## 2. Hostingga joylash
Python 3.11 yoki 3.12 tavsiya qilinadi.

```bash
pip install -r requirements.txt
```

`.env.example` faylini `.env` deb nusxalab, kalitlarni kiriting. Hosting panelida environment variables qo‘llansa, kalitlarni o‘sha yerga kiriting. Kod `.env` faylini avtomatik o‘qimaydi; kalitlarni hosting environment variables bo‘limida kiriting.

Linux serverda misol:
```bash
export BOT_TOKEN="Telegram token"
export JAMENDO_CLIENT_ID="Jamendo Client ID"
export AUDD_TOKEN="AudD token"
export OPENAI_API_KEY="OpenAI API key"
python bot.py
```

Hostingda `python bot.py` doimiy ishlaydigan worker/process sifatida ishga tushsin. SQLite bazasi (`music_bot.db`) saqlanib qolishi kerak; ephemeral diskli hostingda persistent disk ulang.

## 3. Cheklovlar
- Jamendo katalogida har qanday mashhur qo‘shiq bo‘lmasligi mumkin.
- AudD musiqani ishonchli aniqlashi uchun videoda musiqa eshitilishi kerak; juda uzun fayllar yoki katta fayllar hosting/API limitlariga bog‘liq.
- Telegram bot profilining yuqorisida Telegram ilovasidagi umumiy bot sahifasiga o‘zingiz xohlagan “11 200 oylik foydalanuvchi” yozuvini doimiy joylashtirib bo‘lmaydi. Kod `/start` va javoblarda haqiqiy so‘nggi 30 kunlik faol foydalanuvchilar sonini ko‘rsatadi.
- Birinchi marta ishga tushirishdan oldin API kalitlarini tekshiring. Kalitlarni hech kimga yubormang.
