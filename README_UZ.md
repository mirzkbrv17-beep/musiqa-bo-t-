# Musiqa Bot — o‘rnatish

## Nimalar qiladi?
- Qo‘shiq nomi bo‘yicha Internet Archive ochiq audio katalogidan 10 tagacha variant qidiradi.
- Tanlangan material aniq Public Domain yoki Creative Commons litsenziyasiga ega bo‘lsa va audio fayli mavjud bo‘lsa, uni Telegramga yuboradi.
- Ovozli xabarda aytilgan nomni matnga aylantirish uchun `OPENAI_API_KEY` ishlatadi.
- Video/audio ichidagi musiqani tanish uchun `AUDD_TOKEN` ishlatadi.
- So‘nggi 30 kun ichida faol foydalanuvchilar sonini hisoblaydi.

## API kalitlari
Musiqa qidirish uchun Jamendo Client ID kerak emas. Botni boshlang‘ich holatda ishlatish uchun faqat `BOT_TOKEN` kerak. Ovoz va video funksiyalari uchun `OPENAI_API_KEY` va `AUDD_TOKEN` ixtiyoriy, ammo zarur bo‘lishi mumkin.

- Telegram tokeni: Telegramdagi @BotFather
- AudD: https://audd.io/
- OpenAI API key: https://platform.openai.com/api-keys

## Hosting
Python 3.11 yoki 3.12 tavsiya qilinadi.

```bash
pip install -r requirements.txt
python bot.py
```

Hosting panelining Environment Variables bo‘limiga `BOT_TOKEN` kiriting. Ovoz/video funksiyalari kerak bo‘lsa, `AUDD_TOKEN` va `OPENAI_API_KEY` ni ham qo‘shing. `music_bot.db` bazasi saqlanib qoladigan diskdan foydalaning.

## Muhim cheklovlar
- Bu versiya Jamendo Client ID talab qilmaydi; Internet Archive ochiq audio katalogidan qidiradi.
- Internet Archive’da barcha mashhur tijoriy qo‘shiqlar bo‘lmaydi. Bot faqat ochiq litsenziyasi aniqlangan va mos audio fayli bor materiallarni yuborishga urinadi.
- Video tanish va ovozni matnga aylantirish tashqi xizmatlar orqali amalga oshadi; ular API kaliti, internet va xizmat tarifini talab qilishi mumkin.
- Bot profilining o‘zida Telegram ko‘rsatadigan oylik foydalanuvchilar yozuvini boshqarib bo‘lmaydi. Bot javoblarida haqiqiy oxirgi 30 kunlik faol foydalanuvchilar soni ko‘rsatiladi.

## Kutubxonalarni avtomatik o‘rnatish
- Windows kompyuterda `start.bat` faylini ishga tushiring. U `requirements.txt` ichidagi kutubxonalarni o‘rnatib, botni ochadi.
- Linux hostingda Build Command: `pip install -r requirements.txt`; Start Command: `python bot.py`.
- `BOT_TOKEN` ni hostingning Environment Variables bo‘limiga kiriting.
