import discord
from discord.ext import commands
from huggingface_hub import InferenceClient
import asyncio
import logging
from dotenv import load_dotenv
import os

# Load variables from .env
load_dotenv()

# Logging things
logging.basicConfig(level=logging.INFO)

# Load API and Tokens from .env
api_key = os.getenv("API_KEY")
bot_token = os.getenv("DISCORD_TOKEN")

if not api_key or not bot_token:
    raise ValueError("Pastikan file .env berisi HF_API_KEY dan DISCORD_BOT_TOKEN.")

# Inisialisasi client dengan API key
hf_client = InferenceClient(api_key=api_key)

# Inisialisasi bot
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

# Menyimpan riwayat percakapan untuk setiap pengguna
conversation_history = {}

# Fungsi untuk mendapatkan respons chatbot
async def get_chatbot_response(user_input, user_id):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    # Tambahkan pesan pengguna ke riwayat
    conversation_history[user_id].append({"role": "user", "content": user_input})

    # Kirimkan pesan dan riwayat ke model
    try:
        completion = await asyncio.to_thread(
            hf_client.chat.completions.create,
            model="Qwen/Qwen2.5-Coder-32B-Instruct",  # Model AI yang akan dipakai
            messages=conversation_history[user_id],
            max_tokens=1500
        )
        # Ambil respons dan tambahkan ke riwayat
        response = completion.choices[0].message["content"]
        conversation_history[user_id].append({"role": "assistant", "content": response})

        # Batasi panjang riwayat yang akan disimpan di memori sebayak > n
        if len(conversation_history[user_id]) > 30:
            conversation_history[user_id] = conversation_history[user_id][-30:]

        return response
    except Exception as e:
        logging.error(f"Error saat memanggil API: {e}")
        return "Maaf, terjadi kesalahan saat memproses permintaan Anda."

# Message split function, Discord has limit of 2000 characters  
def split_message(response, max_length=2000):
    """
    Memecah pesan menjadi bagian lebih kecil dengan mempertahankan struktur
    blok kode (```) dan header (###), serta memisahkan bagian yang diawali dengan **bold**.
    Baris kosong akan ditambahkan sebelum awal blok kode baru.
    """
    lines = response.splitlines()  # Pisahkan menjadi baris
    parts = []
    current_part = []
    current_length = 0
    inside_code_block = False  # Menandai apakah kita berada dalam blok kode

    for line in lines:
        # Periksa apakah baris ini memulai atau mengakhiri blok kode
        if line.strip().startswith("```"):
            if not inside_code_block:
                # Tambahkan baris kosong sebelum memulai blok kode baru
                if current_part:
                    current_part.append("")  # Baris kosong sebelum ``` jika ada isi sebelumnya
                    current_length += 1
                
            current_part.append(line)
            current_length += len(line) + 1
            inside_code_block = not inside_code_block  # Ubah status blok kode
            continue

        # Periksa apakah baris ini adalah header atau **bold**
        if line.strip().startswith("###") or line.strip().startswith("**"):
            if current_part:
                parts.append("\n".join(current_part))
                current_part = []
                current_length = 0
            current_part.append(line)
            current_length += len(line) + 1
            continue

        # Jika menambahkan baris ini tidak melebihi panjang maksimum, tambahkan
        if current_length + len(line) + 1 <= max_length:
            current_part.append(line)
            current_length += len(line) + 1
        else:
            # Simpan bagian saat ini
            if inside_code_block:
                current_part.append("```")  # Akhiri blok kode
            parts.append("\n".join(current_part))
            current_part = []
            current_length = 0
            if inside_code_block:
                current_part.append("```")  # Mulai blok kode baru
                current_length += len("```") + 1
            current_part.append(line)
            current_length += len(line) + 1

    # Tambahkan bagian terakhir
    if current_part:
        if inside_code_block:
            current_part.append("```")  # Pastikan blok kode ditutup
        parts.append("\n".join(current_part))

    return [part for part in parts if part.strip()]


# Event handler for messaging
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    logging.info(f"Pesan diterima: {message.content}")

    async with message.channel.typing():
        await asyncio.sleep(2)

        # Dapatkan respons dari model
        bot_response = await get_chatbot_response(message.content, message.author.id)

        # Membagi respons menjadi bagian lebih kecil
        response_parts = split_message(bot_response)

        # Kirimkan setiap bagian
        for part in response_parts:
            if part.strip():  # Pastikan bagian tidak kosong
                await message.reply(part, mention_author=False)

# This things Run the bot
try:
    client.run(bot_token)
except Exception as e:
    logging.error(f"Bot mengalami error: {e}")
