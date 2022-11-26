import asyncio
import sqlite3
import os
import re
import dhash
import time
import imghdr
import hashlib

from io import BytesIO
from PIL import Image
from amiyabot import AmiyaBot, Message, Chain, log , PluginInstance, Event, BotAdapterProtocol
from amiyabot.network.download import download_async

curr_dir = os.path.dirname(__file__)
max_disc = 5
max_static_image_threhold = 50 * 1024

emoji_collect_enabled = True

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
                MESSAGE_ID TEXT NOT NULL,
                SEND_COUNT      INT     NOT NULL,
                SEND_TIME       NUMBER     NOT NULL,
                CHANNEL_ID      TEXT    NOT NULL,
                IMAGE_TYPE      TEXT    NOT NULL,
                IMAGE_CAT      TEXT    NOT NULL,
                LAST_SENDER     TEXT    NOT NULL);''')

            c.execute('''CREATE TABLE RECALL_IMAGE
                (IMAGE_HASH     TEXT    NOT NULL,
                MESSAGE_ID TEXT NOT NULL,
                RECALL_TIME       NUMBER     NOT NULL,
                CHANNEL_ID      TEXT    NOT NULL,
                IMAGE_TYPE      TEXT    NOT NULL,
                IMAGE_CAT      TEXT    NOT NULL,
                SENDER     TEXT    NOT NULL);''')

            
            c.execute('''CREATE TABLE PLUGIN_CONFIG
                (FUNCTION_NAME     TEXT    NOT NULL,
                CURRENT_STATE TEXT NOT NULL,
                CHANNEL_ID      TEXT    NOT NULL);''')

            c.execute('''INSERT INTO PLUGIN_CONFIG 
            (FUNCTION_NAME,CURRENT_STATE,CHANNEL_ID) VALUES
            ('emoji_collect_enabled','True','ALL')
            ''')
            
            conn.commit()
        else:
            conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
            c = conn.cursor()
            c.execute("SELECT CURRENT_STATE FROM PLUGIN_CONFIG WHERE FUNCTION_NAME = 'emoji_collect_enabled' AND CHANNEL_ID = ?",['ALL'])
            emoji_collect_enabled = c.fetchall()[0][0] == 'True'



bot = EmojiStatPluginInstance(
    name='图片记录员',
    version='1.0',
    plugin_id='amiyabot-hsyhhssyy-emoji-stat',
    plugin_type='',
    description='让兔兔可以收集群友的消息图片，统计常用emoji，和在群友火星了的时候提醒他们。',
    document=f'{curr_dir}/README.md'
)

async def get_config(config_name,channel_id,connection,default_value)
    c = connection.cursor()
    c.execute("SELECT CURRENT_STATE FROM PLUGIN_CONFIG WHERE FUNCTION_NAME = ? AND CHANNEL_ID = ?",[config_name,channel_id])
    rows = c.fetchall()
    if len(rows) <= 0:
        # 写入该值
        if default_value == True:
            write_value = 'True'
        else:
            write_value = 'False'

        c.execute('''INSERT INTO PLUGIN_CONFIG 
            (FUNCTION_NAME,CURRENT_STATE,CHANNEL_ID) VALUES (?,?,?)''',[config_name,write_value,channel_id])
        return default_value
    else:
        return rows[0][0] == 'True'

async def any_talk(data: Message):

    #计算所有的Hash
    for image_item in data.image:
        imgBytes = await download_async(image_item)
        if imgBytes:
            image = BytesIO(imgBytes)
            try:
                image_type = imghdr.what(None,imgBytes)
                
                length = image.getbuffer().nbytes

                if length > max_static_image_threhold and image_type != 'gif':
                    hash_value = dhash.dhash_int(Image.open(image),16)
                    file_path = f'{curr_dir}/../../resource/emoji-stat/image/{hash_value}'
                else:
                    hash_value = hashlib.md5(imgBytes).hexdigest()
                    file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{hash_value}'

                with open(file_path, mode='wb+') as src:
                    src.write(imgBytes)


                if length > max_static_image_threhold and image_type != 'gif':
                    await check_image(hash_value, file_path, image_type, data)
                else:
                    await check_emoji(hash_value, file_path, image_type, data)

            except OSError:
                continue

    return False,0

async def check_emoji(hash_value, file_path,image_type, data):
    
    # log.info(f'this file {file_path} is: {image_type} as emoji')
    # emoji使用文件hash而不是图像灰度hash

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return
    
    user_id = data.user_id
    channel_id = data.channel_id
    now = time.time()
    c = conn.cursor()

    c.execute("select SEND_TIME from EMOJI_STAT where IMAGE_HASH = ? and CHANNEL_ID = ? and IMAGE_CAT = 'EMOJI'",[ f'{hash_value}',channel_id])

    all_rows = c.fetchall()
    if len(all_rows) > 0:
        l_time = all_rows[0][0]

        c.execute("UPDATE EMOJI_STAT SET SEND_COUNT = SEND_COUNT +1,SEND_TIME = ?,LAST_SENDER= ?,MESSAGE_ID=? where IMAGE_HASH = ? and CHANNEL_ID = ? and IMAGE_CAT = 'EMOJI'",
            [now, user_id,data.message_id, f'{hash_value}',channel_id])
        
        conn.commit()
    else:

        c.execute("INSERT INTO EMOJI_STAT (IMAGE_HASH,SEND_TIME,SEND_COUNT,LAST_SENDER,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,MESSAGE_ID) values (?,?,1,?,?,?,'EMOJI',?)" ,
            [f'{hash_value}',now,user_id,channel_id,image_type,data.message_id])
        conn.commit()

async def check_image(hash_value, file_path,image_type, data):

    # log.info(f'this file {file_path} is: {image_type} as image')

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return
    
    user_id = data.user_id
    channel_id = data.channel_id
    now = time.time()
    delta = now - 5 * 60 * 60
    
    c = conn.cursor()
    c.execute("SELECT SEND_TIME from EMOJI_STAT where IMAGE_HASH = ? and CHANNEL_ID = ? AND IMAGE_CAT = 'IMAGE'",[f'{hash_value}',channel_id])

    all_rows = c.fetchall()
    if len(all_rows) > 0:
        l_time = all_rows[0][0]

        if l_time > delta:
            await data.send(Chain(data).text(f'博士，这张图已经在{time.strftime("%H:%M:%S",time.localtime(l_time))}水过了。'))

        c.execute("UPDATE EMOJI_STAT SET SEND_COUNT = SEND_COUNT +1,SEND_TIME = ?,LAST_SENDER= ?,MESSAGE_ID = ? where IMAGE_HASH = ? and CHANNEL_ID = ? AND IMAGE_CAT = 'IMAGE'",
            [now, user_id,data.message_id, f'{hash_value}',channel_id])
        
        conn.commit()
    else:
        #进行hash比较
        c.execute("select IMAGE_HASH,SEND_TIME from EMOJI_STAT where SEND_TIME > ?  and CHANNEL_ID = ? AND IMAGE_CAT = 'IMAGE'",[delta,channel_id])
        for row in c:
            compare_hash =  int(row[0])
            diff = dhash.get_num_bits_different(hash_value, compare_hash)
            if diff <= max_disc:
                await data.send(Chain(data).text(f'博士，这张图已经在{time.strftime("%H:%M:%S",time.localtime(row[1]))}水过了。'))
                break

        c.execute("INSERT INTO EMOJI_STAT (IMAGE_HASH,SEND_TIME,SEND_COUNT,LAST_SENDER,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,MESSAGE_ID) values (?,?,1,?,?,?,'IMAGE',?)" ,
            [f'{hash_value}',now,user_id,channel_id,image_type,data.message_id])
        conn.commit()

@bot.on_message(verify=any_talk, check_prefix=False)
async def _(data: Message):
    return

@bot.on_message(keywords=['查看Emoji','查看高频图'], level = 5)
async def check_wordcloud(data: Message):
    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    channel_id = data.channel_id

    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,SEND_COUNT,IMAGE_TYPE,IMAGE_CAT from EMOJI_STAT where CHANNEL_ID = ? AND IMAGE_CAT = 'EMOJI' ORDER BY SEND_COUNT DESC",[channel_id])
    
    image_order = 0

    for row in c:
        if image_order > 10:
            break
        image_order = image_order + 1
        
        file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row[0]}' 
        send_count = row[1]
        await data.send(Chain(data, at=False).text(f'博士，群内Emoji第{image_order}名被发送过{send_count}次，它是：').image(file_path))


@bot.on_event('GroupRecallEvent')
async def _(event: Event,instance):
    data = event.data
    message_id = data['messageId']

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    if not recall_store_enabled:
        return

    log.info(f'recall message: {data.keys()}  {dir(event)} {dir(instance)}')

    now = time.time()

    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,LAST_SENDER from EMOJI_STAT where MESSAGE_ID = ?",[message_id])
    
    for row in c:
        # 写入Recall表
        c.execute("INSERT INTO RECALL_IMAGE (IMAGE_HASH,MESSAGE_ID,RECALL_TIME,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,SENDER) values (?,?,?,?,?,?,?)" ,
                [f'{row[0]}',message_id,now,row[1],row[2],row[3],row[4]])
    
    conn.commit()

    await instance.send_message(Chain().at(row[4]).text(f'博士，撤回也没用哦，兔兔已经看见啦。'),channel_id=row[1])
    


@bot.on_message(keywords=['兔兔查看撤回图片'], level = 5)
async def _(data: Message):

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    # 回溯时间，单位为秒
    now = time.time()
    time_delat = now - 60 * 60

    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,CHANNEL_ID,SENDER,RECALL_TIME,IMAGE_CAT from RECALL_IMAGE where RECALL_TIME > ? ",[time_delat])
    for row in c:
        if row[4] == 'EMOJI':
            file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row[0]}'
        else:
            file_path = f'{curr_dir}/../../resource/emoji-stat/image/{row[0]}'
        

        await data.send(Chain(data).text(f'频道{row[1]}的用户{row[2]}在{time.strftime("%H:%M:%S",time.localtime(row[3]))}撤回了如下图片:').image(file_path))
    
@bot.on_message(keywords=['兔兔查看撤回图片'], level = 5)
async def _(data: Message):