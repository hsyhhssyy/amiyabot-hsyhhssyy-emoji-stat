import asyncio
import sqlite3
import os
import re
import dhash
import time
import hashlib

from io import BytesIO
from PIL import Image
from amiyabot import AmiyaBot, Message, Chain, log , PluginInstance, Event, BotAdapterProtocol
from amiyabot.network.download import download_async

from .imghdr import what

curr_dir = os.path.dirname(__file__)
max_disc = 5
max_static_image_threhold = 50 * 1024

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
                CHANNEL_NAME      TEXT    ,
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
        
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
        c = conn.cursor()

        # v1.1 ???????????????
        c.execute('SELECT * FROM SQLITE_MASTER WHERE TBL_NAME = ?',['USER_STAT'])
        table_check = c.fetchall()
        if len(table_check) <=0 :
             c.execute('''CREATE TABLE USER_STAT
                (USER_ID     TEXT    NOT NULL,
                USER_NICKNAME TEXT NOT NULL,
                CHANNEL_ID     TEXT    NOT NULL,
                IMAGE_COUNT INT     NOT NULL,
                IMAGE_SIZE       INT     NOT NULL,
                EMOJI_COUNT      INT     NOT NULL,
                EMOJI_SIZE      INT     NOT NULL);''')

        conn.commit()

bot = EmojiStatPluginInstance(
    name='???????????????',
    version='1.4',
    plugin_id='amiyabot-hsyhhssyy-emoji-stat',
    plugin_type='',
    description='?????????????????????????????????????????????????????????emoji????????????????????????????????????????????????\n1.3??????????????????????????????????????????????????????imghdr?????????',
    document=f'{curr_dir}/README.md'
)

async def get_config(config_name,channel_id,default_value):

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        connection = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return default_value

    c = connection.cursor()
    c.execute("SELECT CURRENT_STATE FROM PLUGIN_CONFIG WHERE FUNCTION_NAME = ? AND CHANNEL_ID = ?",[config_name,channel_id])
    rows = c.fetchall()
    if len(rows) <= 0:
        # ????????????
        if default_value == True:
            write_value = 'True'
        else:
            write_value = 'False'

        c.execute('''INSERT INTO PLUGIN_CONFIG 
            (FUNCTION_NAME,CURRENT_STATE,CHANNEL_ID) VALUES (?,?,?)''',[config_name,write_value,channel_id])
        connection.commit()
        log.info(f"?????????????????????{config_name} {write_value} {channel_id}");
        return default_value
    else:
        return rows[0][0] == 'True'

async def set_config(config_name,channel_id,value):

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        connection = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    if value == True:
        write_value = 'True'
    else:
        write_value = 'False'
        
    c = connection.cursor()
    c.execute("SELECT CURRENT_STATE FROM PLUGIN_CONFIG WHERE FUNCTION_NAME = ? AND CHANNEL_ID = ?",[config_name,channel_id])
    rows = c.fetchall()
    if len(rows) <= 0:
        # ????????????
        c.execute('''INSERT INTO PLUGIN_CONFIG 
            (FUNCTION_NAME,CURRENT_STATE,CHANNEL_ID) VALUES (?,?,?)''',[config_name,write_value,channel_id])
    else:
        c.execute("UPDATE PLUGIN_CONFIG SET CURRENT_STATE = ? WHERE FUNCTION_NAME = ? AND CHANNEL_ID = ?",[write_value, config_name,channel_id])

    connection.commit()

async def any_talk(data: Message):

    channel_id = data.channel_id
    emoji_collect_enabled = await get_config('emoji_collect_enabled',channel_id,True)
    martian_detect_enabled = await get_config('martian_detect_enabled',channel_id,True)
    recall_spy_enabled = await get_config('recall_spy_enabled',channel_id,False)

    #???????????????Hash
    for image_item in data.image:
        imgBytes = await download_async(image_item)
        if imgBytes:
            image = BytesIO(imgBytes)
            try:
                image_type = what(None,imgBytes)
                
                length = image.getbuffer().nbytes

                if length > max_static_image_threhold and image_type != 'gif':
                    # ?????????????????????
                    if not martian_detect_enabled and not recall_spy_enabled:
                        continue
                    
                    hash_value = dhash.dhash_int(Image.open(image),16)
                    file_path = f'{curr_dir}/../../resource/emoji-stat/image/{hash_value}'

                    with open(file_path, mode='wb+') as src:
                        src.write(imgBytes)

                    await check_image(hash_value, file_path, image_type, data)
                else:

                    if not emoji_collect_enabled:
                        continue

                    hash_value = hashlib.md5(imgBytes).hexdigest()
                    file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{hash_value}'

                    with open(file_path, mode='wb+') as src:
                        src.write(imgBytes)

                    await check_emoji(hash_value, file_path, image_type, data)

            except OSError:
                continue

    return False,0

async def check_emoji(hash_value, file_path,image_type, data):
    
    # log.info(f'this file {file_path} is: {image_type} as emoji')
    # emoji????????????hash?????????????????????hash

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return
    
    user_id = data.user_id
    channel_id = data.channel_id
    now = time.time()
    c = conn.cursor()

    emoji_collect_enabled = await get_config('emoji_collect_enabled',channel_id,True)
    if not emoji_collect_enabled:
        return

    c.execute("SELECT * FROM USER_STAT WHERE USER_ID = ? AND CHANNEL_ID = ?",[ user_id,channel_id])
    if len(c.fetchall())==0:
        c.execute('INSERT INTO USER_STAT (USER_ID,USER_NICKNAME,CHANNEL_ID,IMAGE_COUNT,IMAGE_SIZE,EMOJI_COUNT,EMOJI_SIZE) VALUES (?,?,?,0,0,0,0)',[user_id,data.nickname,channel_id])
    
    if os.path.exists(file_path):
        stats = os.stat(file_path)
        total_size = stats.st_size
    else:
        total_size = 0
    c.execute('UPDATE USER_STAT SET EMOJI_COUNT = EMOJI_COUNT + 1, EMOJI_SIZE = EMOJI_SIZE + ? , USER_NICKNAME = ? WHERE USER_ID = ? AND CHANNEL_ID = ?',[total_size,data.nickname,user_id,channel_id])

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

    c.execute("SELECT * FROM USER_STAT WHERE USER_ID = ? AND CHANNEL_ID = ?",[ user_id,channel_id])
    if len(c.fetchall())==0:
        c.execute('INSERT INTO USER_STAT (USER_ID,USER_NICKNAME,CHANNEL_ID,IMAGE_COUNT,IMAGE_SIZE,EMOJI_COUNT,EMOJI_SIZE) VALUES (?,?,?,0,0,0,0)',[user_id,data.nickname,channel_id])

    if os.path.exists(file_path):
        stats = os.stat(file_path)
        total_size = stats.st_size
    else:
        total_size = 0
    c.execute('UPDATE USER_STAT SET IMAGE_COUNT = IMAGE_COUNT + 1, IMAGE_SIZE = IMAGE_SIZE + ? , USER_NICKNAME = ? WHERE USER_ID = ? AND CHANNEL_ID = ?',[total_size,data.nickname,user_id,channel_id])

    martian_detect_enabled = await get_config('martian_detect_enabled',channel_id,True)
    if not martian_detect_enabled:
        return

    c.execute("SELECT SEND_TIME from EMOJI_STAT where IMAGE_HASH = ? and CHANNEL_ID = ? AND IMAGE_CAT = 'IMAGE'",[f'{hash_value}',channel_id])

    all_rows = c.fetchall()
    if len(all_rows) > 0:
        l_time = all_rows[0][0]

        if l_time > delta:
            await data.send(Chain(data).text(f'???????????????????????????{time.strftime("%H:%M:%S",time.localtime(l_time))}????????????'))

        c.execute("UPDATE EMOJI_STAT SET SEND_COUNT = SEND_COUNT +1,SEND_TIME = ?,LAST_SENDER= ?,MESSAGE_ID = ? where IMAGE_HASH = ? and CHANNEL_ID = ? AND IMAGE_CAT = 'IMAGE'",
            [now, user_id,data.message_id, f'{hash_value}',channel_id])
        
        conn.commit()
    else:
        #??????hash??????
        c.execute("select IMAGE_HASH,SEND_TIME from EMOJI_STAT where SEND_TIME > ?  and CHANNEL_ID = ? AND IMAGE_CAT = 'IMAGE'",[delta,channel_id])
        for row in c:
            compare_hash =  int(row[0])
            diff = dhash.get_num_bits_different(hash_value, compare_hash)
            if diff <= max_disc:
                await data.send(Chain(data).text(f'???????????????????????????{time.strftime("%H:%M:%S",time.localtime(row[1]))}????????????'))
                break

        c.execute("INSERT INTO EMOJI_STAT (IMAGE_HASH,SEND_TIME,SEND_COUNT,LAST_SENDER,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,MESSAGE_ID) values (?,?,1,?,?,?,'IMAGE',?)" ,
            [f'{hash_value}',now,user_id,channel_id,image_type,data.message_id])
        conn.commit()

@bot.on_message(verify=any_talk, check_prefix=False)
async def _(data: Message):
    return

@bot.on_event('GroupRecallEvent')
async def _(event: Event,instance):
    data = event.data
    message_id = data['messageId']

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    group = data['group']

    log.info(f'recall message: {message_id} {group} ')

    recall_spy_enabled = await get_config('recall_spy_enabled',group["id"],False)
    if not recall_spy_enabled:
        return

    now = time.time()

    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,LAST_SENDER from EMOJI_STAT where MESSAGE_ID = ?",[message_id])
    
    user_id = None

    for row in c:
        # ??????Recall???
        c.execute("INSERT INTO RECALL_IMAGE (IMAGE_HASH,MESSAGE_ID,RECALL_TIME,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,SENDER,CHANNEL_NAME) values (?,?,?,?,?,?,?,?)" ,
                [f'{row[0]}',message_id,now,row[1],row[2],row[3],row[4],group["name"]])
        user_id = row[4]
    
    conn.commit()
    if user_id:
        await instance.send_message(Chain().at(user_id).text(f'??????????????????????????????????????????????????????'),channel_id=row[1])
    

@bot.on_message(keywords=['??????Emoji','???????????????','??????Emoji','???????????????'], level = 5)
async def _(data: Message):
    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    channel_id = data.channel_id

    emoji_collect_enabled = await get_config('emoji_collect_enabled',channel_id,True)

    if not emoji_collect_enabled:
        return

    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,SEND_COUNT,IMAGE_TYPE,IMAGE_CAT from EMOJI_STAT where CHANNEL_ID = ? AND IMAGE_CAT = 'EMOJI' ORDER BY SEND_COUNT DESC",[channel_id])
    
    image_order = 0

    for row in c:
        if image_order >= 10:
            break
        image_order = image_order + 1
        
        file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row[0]}' 
        send_count = row[1]
        await data.send(Chain(data, at=False).text(f'???????????????Emoji???{image_order}???????????????{send_count}???????????????').image(file_path))


@bot.on_message(keywords=['?????????'], level = 5)
async def _(data: Message):
    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    channel_id = data.channel_id
    c = conn.cursor()

    c.execute("SELECT USER_ID,USER_NICKNAME,EMOJI_COUNT,IMAGE_COUNT from USER_STAT where CHANNEL_ID = ? ORDER BY IMAGE_COUNT+EMOJI_COUNT DESC",[channel_id])
    
    image_order = 0

    message_to_send = '????????????????????????????????????\n'

    for row in c:
        if image_order > 5:
            break
        image_order = image_order + 1

        message_to_send = message_to_send + f'???{image_order}??????"{row[1]}"??????\t?????????{row[2]+row[3]}????????????\n'

    await data.send(Chain(data, at=False).text(message_to_send))
    
    c.execute("SELECT USER_ID,USER_NICKNAME,EMOJI_SIZE,IMAGE_SIZE from USER_STAT where CHANNEL_ID = ? ORDER BY EMOJI_SIZE+IMAGE_SIZE DESC",[channel_id])

    image_order = 0
    
    message_to_send = '????????????????????????????????????\n'

    for row in c:
        if image_order > 5:
            break
        image_order = image_order + 1

        size = row[2]+row[3]

        size_text = f'{size}Byte'
        if size > 1024 * 1024 * 1024:
            size_text = f'{int((row[2]+row[3])/1024/1024/1024)}GB'
        elif size > 1024 * 1024:
            size_text = f'{int((row[2]+row[3])/1024/1024)}MB'
        elif size > 1024:
            size_text = f'{int((row[2]+row[3])/1024)}KB'

        message_to_send = message_to_send + f'???{image_order}??????"{row[1]}"??????\t?????????{size_text}????????????\n'

    await data.send(Chain(data, at=False).text(message_to_send))

@bot.on_message(keywords=['??????????????????'],check_prefix = False, direct_only = True)
async def _(data: Message):

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    match = re.search('??????????????????(\d*?)???', data.text_digits)
    if match:
        minute_delta = int(match.group(1))
    else:
        return Chain(data).text(f'?????????????????? ??????????????????X??? ??????????????????????????????')

    # ???????????????????????????
    now = time.time()
    if minute_delta > 24 * 60:
        minute_delta = 24 * 60
    time_delta = now - minute_delta * 60

    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,CHANNEL_ID,SENDER,RECALL_TIME,IMAGE_CAT from RECALL_IMAGE where RECALL_TIME > ? ",[time_delta])
    image_count = 0
    for row in c:
        if row[4] == 'EMOJI':
            file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row[0]}'
        else:
            file_path = f'{curr_dir}/../../resource/emoji-stat/image/{row[0]}'
        
        image_count += 1
        await data.send(Chain(data).text(f'??????{row[1]}?????????{row[2]}???{time.strftime("%H:%M:%S",time.localtime(row[3]))}?????????????????????:').image(file_path))
    
    return Chain(data).text(f'??????????????????????????????{minute_delta}????????????{image_count}????????????')

@bot.on_message(keywords=['????????????Emoji','????????????Emoji'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('emoji_collect_enabled',channel_id,False)

    return Chain(data).text(f'?????????????????????????????????Emoji??????') 

@bot.on_message(keywords=['????????????Emoji','????????????Emoji','????????????Emoji'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('emoji_collect_enabled',channel_id,True)

    return Chain(data).text(f'?????????????????????????????????Emoji??????') 

@bot.on_message(keywords=['???????????????','???????????????'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('martian_detect_enabled',channel_id,False)

    return Chain(data).text(f'??????????????????????????????????????????????????????????????????') 


@bot.on_message(keywords=['???????????????','???????????????'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('martian_detect_enabled',channel_id,True)

    return Chain(data).text(f'?????????????????????????????????????????????????????????') 

@bot.on_message(keywords=['????????????','????????????'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('recall_spy_enabled',channel_id,False)

    return Chain(data).text(f'????????????????????????????????????????????????????????????') 


@bot.on_message(keywords=['????????????','????????????'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('recall_spy_enabled',channel_id,True)

    return Chain(data).text(f'???????????????????????????????????????????????????????????????????????????????????????24????????????') 

@bot.on_message(keywords=['????????????????????????'], level = 10)
async def _(data: Message):

    channel_id = data.channel_id
    
    martian_detect_enabled =await  get_config('martian_detect_enabled',channel_id,True)
    emoji_collect_enabled = await get_config('emoji_collect_enabled',channel_id,True)
    recall_spy_enabled =await  get_config('recall_spy_enabled',channel_id,False)

    return Chain(data).text(f'?????????????????????????????????:\nEmoji?????????{"??????" if emoji_collect_enabled==True else "??????"}\n??????????????????{"??????" if martian_detect_enabled==True else "??????"}\n???????????????{"??????" if recall_spy_enabled==True else "??????"}') 

@bot.on_message(keywords=['????????????'],check_prefix = False, direct_only = True)
async def _(data: Message):
    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    match = re.search('????????????(\d*?)???', data.text_digits)
    if match:
        date_delta = int(match.group(1))
    else:
        return Chain(data).text(f'?????????????????? ????????????X??? ??????????????????????????????')

    now = time.time()
    delta = now - date_delta * 24 * 3600

    image_to_delete = []
    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,IMAGE_CAT from EMOJI_STAT WHERE SEND_TIME < ?",[delta])
    
    for row in c:
        # ??????Recall???
        image_to_delete.append([row[0],row[1]])

    total_size = 0
    total_count = 0

    for image_info in image_to_delete:
        # ?????????????????????
        c.execute("DELETE from EMOJI_STAT WHERE IMAGE_HASH = ?",[image_info[0]])
        c.execute("DELETE from RECALL_IMAGE WHERE IMAGE_HASH = ?",[image_info[0]])
        # ??????????????????
        if image_info[1] == 'IMAGE':
            file_path = f'{curr_dir}/../../resource/emoji-stat/image/{image_info[0]}'
        else:
            file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{image_info[0]}'

        if os.path.exists(file_path):
            stats = os.stat(file_path)
            total_size += stats.st_size
            total_count += 1
            os.remove(file_path)

    conn.commit()

    return Chain(data).text(f'????????????????????????{date_delta}????????????????????????{total_count}??????????????????{int(total_size/1024/1024)}MB???') 