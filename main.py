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

        # v1.1 加入的新表
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
    name='图片记录员',
    version='1.3',
    plugin_id='amiyabot-hsyhhssyy-emoji-stat',
    plugin_type='',
    description='让兔兔可以收集群友的消息图片，统计常用emoji，和在群友火星了的时候提醒他们。\n1.3版本修复了可执行文件部署时报错找不到imghdr的问题',
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
        # 写入该值
        if default_value == True:
            write_value = 'True'
        else:
            write_value = 'False'

        c.execute('''INSERT INTO PLUGIN_CONFIG 
            (FUNCTION_NAME,CURRENT_STATE,CHANNEL_ID) VALUES (?,?,?)''',[config_name,write_value,channel_id])
        connection.commit()
        log.info(f"写入配置初始值{config_name} {write_value} {channel_id}");
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
        # 写入该值
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

    #计算所有的Hash
    for image_item in data.image:
        imgBytes = await download_async(image_item)
        if imgBytes:
            image = BytesIO(imgBytes)
            try:
                image_type = what(None,imgBytes)
                
                length = image.getbuffer().nbytes

                if length > max_static_image_threhold and image_type != 'gif':
                    # 判定为普通图片
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
    # emoji使用文件hash而不是图像灰度hash

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
        # 写入Recall表
        c.execute("INSERT INTO RECALL_IMAGE (IMAGE_HASH,MESSAGE_ID,RECALL_TIME,CHANNEL_ID,IMAGE_TYPE,IMAGE_CAT,SENDER,CHANNEL_NAME) values (?,?,?,?,?,?,?,?)" ,
                [f'{row[0]}',message_id,now,row[1],row[2],row[3],row[4],group["name"]])
        user_id = row[4]
    
    conn.commit()
    if user_id:
        await instance.send_message(Chain().at(user_id).text(f'博士，撤回也没用哦，兔兔已经看见啦。'),channel_id=row[1])
    

@bot.on_message(keywords=['查看Emoji','查看高频图'], level = 5)
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
        if image_order > 10:
            break
        image_order = image_order + 1
        
        file_path = f'{curr_dir}/../../resource/emoji-stat/emoji/{row[0]}' 
        send_count = row[1]
        await data.send(Chain(data, at=False).text(f'博士，群内Emoji第{image_order}名被发送过{send_count}次，它是：').image(file_path))


@bot.on_message(keywords=['水图王'], level = 5)
async def _(data: Message):
    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    channel_id = data.channel_id
    c = conn.cursor()

    c.execute("SELECT USER_ID,USER_NICKNAME,EMOJI_COUNT,IMAGE_COUNT from USER_STAT where CHANNEL_ID = ? ORDER BY IMAGE_COUNT+EMOJI_COUNT DESC",[channel_id])
    
    image_order = 0

    message_to_send = '发送图片数量的排名如下：\n'

    for row in c:
        if image_order > 5:
            break
        image_order = image_order + 1

        message_to_send = message_to_send + f'第{image_order}名："{row[1]}"博士\t发送过{row[2]+row[3]}张图片。\n'

    await data.send(Chain(data, at=False).text(message_to_send))
    
    c.execute("SELECT USER_ID,USER_NICKNAME,EMOJI_SIZE,IMAGE_SIZE from USER_STAT where CHANNEL_ID = ? ORDER BY EMOJI_SIZE+IMAGE_SIZE DESC",[channel_id])

    image_order = 0
    
    message_to_send = '发送图片大小的排名如下：\n'

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

        message_to_send = message_to_send + f'第{image_order}名："{row[1]}"博士\t发送过{size_text}的图片。\n'

    await data.send(Chain(data, at=False).text(message_to_send))

@bot.on_message(keywords=['查看撤回图片'],check_prefix = False, direct_only = True)
async def _(data: Message):

    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    match = re.search('查看撤回图片(\d*?)分', data.text_digits)
    if match:
        minute_delta = int(match.group(1))
    else:
        return Chain(data).text(f'博士，请发送 查看撤回图片X分 来指定查看的时间哦。')

    # 回溯时间，单位为秒
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
        await data.send(Chain(data).text(f'频道{row[1]}的用户{row[2]}在{time.strftime("%H:%M:%S",time.localtime(row[3]))}撤回了如下图片:').image(file_path))
    
    return Chain(data).text(f'撤回图片列出完毕，在{minute_delta}分内共计{image_count}张图片。')

@bot.on_message(keywords=['关闭收集Emoji','停止收集Emoji'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('emoji_collect_enabled',channel_id,False)

    return Chain(data).text(f'博士，兔兔现在停止收集Emoji啦。') 

@bot.on_message(keywords=['开始收集Emoji','打开收集Emoji','开启收集Emoji'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('emoji_collect_enabled',channel_id,True)

    return Chain(data).text(f'博士，兔兔现在开始收集Emoji啦。') 

@bot.on_message(keywords=['关闭水过了','停止水过了'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('martian_detect_enabled',channel_id,False)

    return Chain(data).text(f'博士，兔兔现在不再关心大家消息是不是灵通啦。') 


@bot.on_message(keywords=['开启水过了','打开水过了'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('martian_detect_enabled',channel_id,True)

    return Chain(data).text(f'博士，兔兔现在要看看谁消息不够灵通啦。') 

@bot.on_message(keywords=['关闭撤回','停止撤回'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('recall_spy_enabled',channel_id,False)

    return Chain(data).text(f'博士，兔兔现在不再记录大家撤回的图片了。') 


@bot.on_message(keywords=['开启撤回','打开撤回'], level = 5)
async def _(data: Message):

    channel_id = data.channel_id
    await set_config('recall_spy_enabled',channel_id,True)

    return Chain(data).text(f'博士，兔兔已经开始记录撤回的图片了，撤回图片会为管理员保存24小时哦。') 

@bot.on_message(keywords=['查看图片记录状态'], level = 10)
async def _(data: Message):

    channel_id = data.channel_id
    
    martian_detect_enabled =await  get_config('martian_detect_enabled',channel_id,True)
    emoji_collect_enabled = await get_config('emoji_collect_enabled',channel_id,True)
    recall_spy_enabled =await  get_config('recall_spy_enabled',channel_id,False)

    return Chain(data).text(f'博士，兔兔当前的状态是:\nEmoji统计：{"打开" if emoji_collect_enabled==True else "关闭"}\n水过了检测：{"打开" if martian_detect_enabled==True else "关闭"}\n撤回记录：{"打开" if recall_spy_enabled==True else "关闭"}') 

@bot.on_message(keywords=['清理图片'],check_prefix = False, direct_only = True)
async def _(data: Message):
    if os.path.exists(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db'):
        conn = sqlite3.connect(f'{curr_dir}/../../resource/emoji-stat/emoji-stat.db')
    else:
        return

    match = re.search('清理图片(\d*?)天', data.text_digits)
    if match:
        date_delta = int(match.group(1))
    else:
        return Chain(data).text(f'博士，请发送 清理图片X天 来指定清理的天数哦。')

    now = time.time()
    delta = now - date_delta * 24 * 3600

    image_to_delete = []
    c = conn.cursor()
    c.execute("SELECT IMAGE_HASH,IMAGE_CAT from EMOJI_STAT WHERE SEND_TIME < ?",[delta])
    
    for row in c:
        # 写入Recall表
        image_to_delete.append([row[0],row[1]])

    total_size = 0
    total_count = 0

    for image_info in image_to_delete:
        # 删掉数据库记录
        c.execute("DELETE from EMOJI_STAT WHERE IMAGE_HASH = ?",[image_info[0]])
        c.execute("DELETE from RECALL_IMAGE WHERE IMAGE_HASH = ?",[image_info[0]])
        # 删掉图片本身
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

    return Chain(data).text(f'博士，兔兔清理了{date_delta}天内的图片，共计{total_count}张，共计大约{int(total_size/1024/1024)}MB。') 