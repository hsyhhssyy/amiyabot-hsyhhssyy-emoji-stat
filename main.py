import asyncio
import sqlite3
import os
import re
import dhash
import time

from io import BytesIO
from PIL import Image
from amiyabot import AmiyaBot, Message, Chain, log , PluginInstance
from amiyabot.network.download import download_async

curr_dir = os.path.dirname(__file__)
max_disc = 25

class EmojiStatPluginInstance(PluginInstance):
    def install(self):
        if not os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji'):
            os.makedirs(f'{curr_dir}/../../resource/emoji-stat/emoji')
        
        if not os.path.exists(f'{curr_dir}/../../resource/emoji-stat/image'):
            os.makedirs(f'{curr_dir}/../../resource/emoji-stat/image')

        if not os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):  
            conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE EMOJI_STAT
                (IMAGE_HASH     TEXT    NOT NULL,
                SEND_COUNT      INT     NOT NULL,
                SEND_TIME       NUMBER     NOT NULL,
                CHANNEL_ID      TEXT    NOT NULL,
                LAST_SENDER     TEXT    NOT NULL);''')
            conn.commit()

bot = EmojiStatPluginInstance(
    name='图片记录员',
    version='1.0',
    plugin_id='amiyabot-hsyhhssyy-emoji-stat',
    plugin_type='',
    description='让兔兔可以收集群友的消息图片并统计emoji和火星图',
    document=f'{curr_dir}/README.md'
)

async def any_talk(data: Message):

    #计算所有的Hash
    for image_item in data.image:
        imgBytes = await download_async(image_item)
        if imgBytes:
            image = BytesIO(imgBytes)
            try:
                hash_value = dhash.dhash_int(Image.open(image))
                
                length = image.getbuffer().nbytes

                if length > 20 * 1024 :
                    file_path = f'{curr_dir}/../../resource/emoji-stat/image/{hash_value}.jpg'
                else:
                    file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{hash_value}.jpg'

                with open(file_path, mode='wb+') as src:
                    src.write(imgBytes)

                if length > 20 * 1024 :
                    await check_image(hash_value, file_path, data)
                else:
                    await check_emoji(hash_value, file_path, data)

                log.info(f'处理了一张图片{file_path}')
            except OSError:
                continue

    return False,0

async def check_emoji(hash_value, file_path, data):
    pass

async def check_image(hash_value, file_path, data):

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return
    
    user_id = data.user_id
    channel_id = data.channel_id
    now = time.time()
    delta = now - 5 * 60 * 60
    
    c = conn.cursor()
    str_hash = f'{hash_value}'
    c.execute("select SEND_TIME from EMOJI_STAT where IMAGE_HASH = ? and CHANNEL_ID = ?",[str_hash,channel_id])

    all_rows = c.fetchall()
    if len(all_rows) > 0:
        l_time = all_rows[0][0]

        if l_time > delta:
            await data.send(Chain(data).text(f'博士，这张图已经在{time.strftime("%H:%M:%S",time.localtime(l_time))}水过了。'))

        c.execute("UPDATE EMOJI_STAT SET SEND_COUNT = SEND_COUNT +1,SEND_TIME = ?,LAST_SENDER= ? where IMAGE_HASH = ? and CHANNEL_ID = ?",
            [now, user_id, f'{hash_value}',channel_id])
        
        conn.commit()
    else:
        #进行hash比较
        c.execute("select IMAGE_HASH,SEND_TIME from EMOJI_STAT where SEND_TIME > ?  and CHANNEL_ID = ?",[delta,channel_id])
        for row in c:
            compare_hash =  int(row[0])
            diff = dhash.get_num_bits_different(hash_value, compare_hash)
            if diff <= max_disc:
                await data.send(Chain(data).text(f'博士，这张图已经在{time.strftime("%H:%M:%S",time.localtime(row[1]))}水过了。'))

        c.execute('INSERT INTO EMOJI_STAT (IMAGE_HASH,SEND_TIME,SEND_COUNT,LAST_SENDER,CHANNEL_ID) values (?,?,1,?,?)' ,
            [f'{hash_value}',now,user_id,channel_id])
        conn.commit()

@bot.on_message(verify=any_talk, check_prefix=False)
async def _(data: Message):
    return
