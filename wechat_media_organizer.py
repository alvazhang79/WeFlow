import requests
import os
import re
import sys
from datetime import datetime
import json
import time

# --- 辅助函数 ---
def get_current_date_str():
    return datetime.now().strftime("%Y%m%d")

def get_current_date_hyphenated_str():
    return datetime.now().strftime("%Y-%m-%d")

# --- 配置常量 (支持命令行参数和环境变量) ---
# 默认配置
API_BASE_URL = os.environ.get("WEFLOW_API_URL", "http://192.168.100.68:5031")
API_TOKEN = os.environ.get("WEFLOW_API_TOKEN", "6zDAqWf8V8JQcu1fBBTrLNQBMq04yZEy")
TARGET_GROUP_NAME = os.environ.get("WEFLOW_GROUP_NAME", "6标监理")
OUTPUT_BASE_DIR = os.environ.get("WEFLOW_OUTPUT_DIR", "/home/wechat/Alva/6标监理")

# 日期范围：从环境变量读取，格式 YYYYMMDD
# 如果没有设置，则使用今天的日期
DEFAULT_START_DATE = os.environ.get("WEFLOW_START_DATE", get_current_date_str())
DEFAULT_END_DATE = os.environ.get("WEFLOW_END_DATE", get_current_date_str())

MESSAGE_MATCH_WINDOW_SECONDS = 300 # 5分钟

# --- 辅助函数 ---

def sanitize_filename(filename):
    """
    清理文件名，移除或替换不允许的特殊字符。
    """
    cleaned_filename = re.sub(r'[\\/:*?"<>|]', '', filename)
    cleaned_filename = re.sub(r'\.+$', '', cleaned_filename)
    cleaned_filename = re.sub(r'\s+', ' ', cleaned_filename).strip()
    if len(cleaned_filename) > 200: # 限制文件名长度，避免过长
        cleaned_filename = cleaned_filename[:200]
    return cleaned_filename

def get_current_date_str():
    """
    获取当前日期字符串，格式 YYYYMMDD。
    """
    return datetime.now().strftime("%Y%m%d")

def get_current_date_hyphenated_str():
    """
    获取当前日期字符串，格式 YYYY-MM-DD。
    """
    return datetime.now().strftime("%Y-%m-%d")

# --- API 交互函数 ---

def get_group_id(group_name: str) -> str | None:
    """
    通过 API 获取指定微信群的 talker ID。
    """
    print(f"正在获取群 '{group_name}' 的 ID...")
    url = f"{API_BASE_URL}/api/v1/sessions"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"keyword": group_name}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and data.get("sessions"):
            for session in data["sessions"]:
                # 精确匹配群名称，且确保是群聊 (通常群ID会是 @chatroom 结尾)
                if session.get("displayName") == group_name and session.get("username", "").endswith("@chatroom"):
                    print(f"找到群 '{group_name}', ID: {session['username']}")
                    return session["username"]
            print(f"未找到群 '{group_name}' 或匹配的群聊。")
            return None
        else:
            print(f"获取群列表失败或无数据: {data.get('error', '未知错误')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求 API 失败: {e}")
        return None

def load_contacts_from_json() -> dict[str, str]:
    """
    从 JSON 文件加载联系人列表。
    优先使用用户提供的 JSON 文件。
    """
    # 查找最新的 JSON 文件
    contacts_dir = "/home"
    json_file = None
    
    # 查找匹配的文件
    for f in os.listdir(contacts_dir):
        if f.startswith("contacts_") and f.endswith(".json"):
            if json_file is None or f > json_file:
                json_file = os.path.join(contacts_dir, f)
    
    if not json_file:
        print("未找到联系人 JSON 文件，将尝试从 API 获取。")
        return {}

    print(f"正在从 JSON 文件加载联系人: {json_file}")
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        contact_map = {}
        if "contacts" in data:
            for contact in data["contacts"]:
                username = contact.get("username")
                # 优先级：remark > displayName > nickname > username
                display_name = contact.get("remark") or contact.get("displayName") or contact.get("nickname") or username
                if username and display_name:
                    contact_map[username] = display_name
        
        print(f"成功从 JSON 文件加载 {len(contact_map)} 个联系人。")
        return contact_map
    except Exception as e:
        print(f"加载 JSON 文件失败: {e}，将尝试从 API 获取。")
        return {}

def get_all_contacts() -> dict[str, str]:
    """
    通过 API 获取所有联系人列表，并返回 username 到 displayName 的映射。
    """
    print("正在获取所有联系人列表...")
    url = f"{API_BASE_URL}/api/v1/contacts"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"limit": 10000} # 获取足够多的联系人

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        contact_map = {}
        if data.get("success") and data.get("contacts"):
            for contact in data["contacts"]:
                username = contact.get("userName")
                # 优先级：remark > nickName > displayName > username
                display_name = contact.get("remark") or contact.get("nickName") or contact.get("displayName") or username
                if username and display_name:
                    contact_map[username] = display_name
            print(f"成功获取 {len(contact_map)} 个联系人。")
        else:
            print(f"获取联系人列表失败或无数据: {data.get('error', '未知错误')}")
        return contact_map
    except requests.exceptions.RequestException as e:
        print(f"请求 API 失败: {e}")
        return {}


def get_today_messages(group_id: str) -> list[dict] | None:
    """
    获取指定群组在指定日期范围内的所有消息，包括图片和视频。
    默认获取今天的消息，可通过环境变量 WEFLOW_START_DATE 和 WEFLOW_END_DATE 自定义。
    """
    start_date = DEFAULT_START_DATE
    end_date = DEFAULT_END_DATE
    
    if start_date and end_date:
        print(f"正在获取群 '{group_id}' 从 {start_date} 到 {end_date} 的消息...")
    else:
        print(f"正在获取群 '{group_id}' 今天的所有消息...")
        
    url = f"{API_BASE_URL}/api/v1/messages"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {
        "talker": group_id,
        "start": start_date,
        "end": end_date,
        "media": 1,  # 确保媒体文件被导出
        "image": 1,  # 确保图片被导出
        "video": 1,  # 确保视频被导出
        "limit": 10000 # 获取足够多的消息
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and data.get("messages"):
            print(f"成功获取 {len(data['messages'])} 条消息。")
            return data["messages"]
        elif not data.get("success"):
            print(f"获取消息失败: {data.get('error', '未知错误')}")
            return None
        else:
            print("今天没有获取到任何消息。")
            return []
    except requests.exceptions.RequestException as e:
        print(f"请求 API 失败: {e}")
        return None

# --- 消息处理类 ---

class MessageInfo:
    """
    统一消息数据结构，方便处理。
    """
    def __init__(self, msg: dict, sender_display_name: str = None):
        self.raw_msg = msg
        self.local_id = msg.get("localId")
        self.server_id = msg.get("serverId")
        self.local_type = msg.get("localType")
        self.create_time = msg.get("createTime") # 毫秒时间戳
        self.timestamp_sec = self.create_time // 1000 # 秒级时间戳
        self.sender_username = msg.get("senderUsername")
        self.sender_display_name = sender_display_name if sender_display_name else self.sender_username # 添加 displayName
        self.content = msg.get("content")
        self.media_type = msg.get("mediaType") # "image" 或 "video"
        self.media_url = msg.get("mediaUrl")
        self.media_local_path = msg.get("mediaLocalPath")
        self.media_file_name = None # 从media_url中解析出的文件名，不含路径
        if self.media_url:
            self.media_file_name = os.path.basename(self.media_url.split('?')[0])

# --- 核心逻辑函数 ---

def match_media_with_text(processed_messages: list[MessageInfo]):
    """
    匹配媒体消息（图片/视频）和对应的文本说明。
    返回一个字典，键为媒体消息的 localId，值为包含媒体信息和说明的字典。
    """
    matched_results = {} # 存储匹配结果 {media_local_id: {'media_info': MessageInfo, 'description': '...', 'sender_display_name': '...'}}
    unmatched_media_queue = [] # 存储等待匹配的媒体消息

    # 遍历已排序的 MessageInfo 对象
    for msg_info in processed_messages:
        if msg_info.local_type in [3, 43] and msg_info.media_url: # 媒体消息 (3:图片, 43:视频)
            unmatched_media_queue.append(msg_info)
        elif msg_info.local_type == 1 and msg_info.content: # 文本消息 (1:文本)
            current_text_message = msg_info
            
            media_to_match_with_text = []

            # 从队列尾部开始向前找，匹配发送人相同且在时间窗口内的媒体
            # 策略：文本消息可以匹配其前面或后面的媒体。这里是从后向前找，先匹配距离最近的媒体。
            i = len(unmatched_media_queue) - 1
            while i >= 0:
                media = unmatched_media_queue[i]
                time_diff = abs(current_text_message.timestamp_sec - media.timestamp_sec)
                
                # 匹配条件：发送人相同，且在时间窗口内
                if media.sender_username == current_text_message.sender_username and \
                   time_diff <= MESSAGE_MATCH_WINDOW_SECONDS:
                    
                    media_to_match_with_text.append(media)
                    # 从队列中移除已匹配的媒体
                    unmatched_media_queue.pop(i)
                elif current_text_message.timestamp_sec > media.timestamp_sec and \
                     (current_text_message.timestamp_sec - media.timestamp_sec) > MESSAGE_MATCH_WINDOW_SECONDS:
                    # 如果当前文本消息在媒体消息之后，但时间差已超出窗口，则停止向前查找
                    break
                elif current_text_message.timestamp_sec < media.timestamp_sec and \
                     (media.timestamp_sec - current_text_message.timestamp_sec) > MESSAGE_MATCH_WINDOW_SECONDS:
                    # 如果当前文本消息在媒体消息之前，但时间差已超出窗口，则停止向前查找
                    break
                
                i -= 1

            # 如果找到了匹配的媒体
            if media_to_match_with_text:
                # 将匹配到的媒体按照原始消息时间顺序排序，确保 -N 后缀的顺序正确
                media_to_match_with_text.sort(key=lambda x: x.create_time)

                if len(media_to_match_with_text) == 1:
                    media_item = media_to_match_with_text[0]
                    matched_results[media_item.local_id] = {
                        'media_info': media_item,
                        'description': current_text_message.content,
                        'sender_display_name': media_item.sender_display_name # 使用 MessageInfo 中已有的 displayName
                    }
                else: # 多媒体单说明
                    for idx, media_item in enumerate(media_to_match_with_text):
                        # 在描述后面加上 "-N" 区分
                        description_with_suffix = f"{current_text_message.content} -{idx + 1}"
                        matched_results[media_item.local_id] = {
                            'media_info': media_item,
                            'description': description_with_suffix,
                            'sender_display_name': media_item.sender_display_name
                        }
    
    # 处理未匹配到的媒体消息 (没有说明文字的图片/视频)
    for media_info in unmatched_media_queue:
        # TODO: 2.4 处理无说明文字的媒体 (当前简化处理)
        #   - 检查水印相机内容 (复杂，需OCR或图像处理库)
        #   - AI 理解图片内容 (复杂，需外部API)
        
        default_description = f"未命名{media_info.media_type}"
        
        # 尝试从原始媒体文件名中获取一些线索作为默认说明
        if media_info.media_file_name:
            name_without_ext = os.path.splitext(media_info.media_file_name)[0]
            if name_without_ext:
                default_description = f"{name_without_ext}"

        # 最终的默认描述
        final_description = f"{default_description} (ID:{media_info.local_id})"

        matched_results[media_info.local_id] = {
            'media_info': media_info,
            'description': final_description,
            'sender_display_name': media_info.sender_display_name
        }
        
    return matched_results


def download_media(media_url: str, save_path: str) -> bool:
    """
    从给定的 URL 下载媒体文件到指定路径。
    动态替换 media_url 中的 127.0.0.1 为 API_BASE_URL 的实际 IP。
    """
    # 解析 API_BASE_URL 获取实际的 host:port
    api_host_port = API_BASE_URL.split('//')[1].split(':')[0] + ':' + API_BASE_URL.split('//')[1].split(':')[1]

    # 将 media_url 中的 127.0.0.1 替换为实际的 API host
    # 确保只替换 host 部分，端口号保持不变
    corrected_media_url = re.sub(r'http://127\.0\.0\.1:(\d+)/', f"http://{api_host_port.split(':')[0]}:\\1/", media_url)
    
    print(f"正在下载媒体文件从 {corrected_media_url} 到 {save_path}...")
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        with requests.get(corrected_media_url, headers=headers, stream=True, timeout=120) as r:
            r.raise_for_status() # 如果状态码不是 2xx，则抛出异常
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"媒体文件下载成功: {save_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载媒体文件失败: {e}")
        return False

def save_media_and_description(matched_media_results: dict):
    """
    根据匹配结果，将媒体文件和说明保存到指定的目录结构中。
    """
    print(f"正在保存媒体文件和说明到基础目录: {OUTPUT_BASE_DIR}")
    today_date_hyphenated_str = get_current_date_hyphenated_str()

    for media_local_id, match_info in matched_media_results.items():
        media_info = match_info['media_info']
        description = match_info['description']
        sender_display_name = match_info['sender_display_name']

        if not media_info.media_url or not media_info.media_file_name:
            print(f"警告: 媒体消息 {media_local_id} 缺少下载 URL 或文件名，跳过。")
            continue

        # 构建目录结构
        # /home/wechat/Alva/6标监理/YYYY-MM-DD/发送人名字/
        date_dir = os.path.join(OUTPUT_BASE_DIR, today_date_hyphenated_str)
        sender_dir = os.path.join(date_dir, sanitize_filename(sender_display_name))
        os.makedirs(sender_dir, exist_ok=True)

        # 构造媒体文件名
        original_extension = os.path.splitext(media_info.media_file_name)[1]
        base_description = re.sub(r' -(\d+)$', '', description).strip() # 移除描述中的文件后缀 "-N"
        media_file_name_base = sanitize_filename(base_description)
        
        # 处理多媒体后缀 -N
        suffix_match = re.search(r' -(\d+)$', description)
        if suffix_match:
            media_file_name_final = f"{media_file_name_base}-{suffix_match.group(1)}{original_extension}"
        else:
            media_file_name_final = f"{media_file_name_base}{original_extension}"

        media_save_path = os.path.join(sender_dir, media_file_name_final)

        # 下载媒体文件
        if not os.path.exists(media_save_path): # 避免重复下载
            download_success = download_media(media_info.media_url, media_save_path)
            if not download_success:
                print(f"跳过保存媒体文件 {media_info.media_url}，因为下载失败。")
                continue
        else:
            print(f"媒体文件已存在，跳过下载: {media_save_path}")

        # 生成说明文本文件
        txt_file_name = f"{today_date_hyphenated_str}-{sanitize_filename(sender_display_name)}.txt"
        txt_save_path = os.path.join(sender_dir, txt_file_name)

        # 将说明内容追加到 txt 文件，确保包含所有媒体的说明
        try:
            with open(txt_save_path, 'a', encoding='utf-8') as f:
                f.write(f"[{media_file_name_final}]: {description}\n")
            print(f"说明已保存/追加到: {txt_save_path}")
        except IOError as e:
            print(f"保存说明文本文件失败 {txt_save_path}: {e}")

def main():
    """
    主函数，协调所有功能的执行。
    """
    print("--- 微信群媒体整理工具启动 ---")

    # 1. 获取目标微信群 ID
    group_id = get_group_id(TARGET_GROUP_NAME)
    if not group_id:
        print("无法获取目标微信群 ID，程序退出。")
        return

    # 2. 优先从 JSON 文件获取联系人显示名称映射，用于美化文件名
    contact_display_name_map = load_contacts_from_json()
    
    # 如果 JSON 文件加载失败，回退到 API 获取
    if not contact_display_name_map:
        print("JSON 文件加载失败或为空，尝试从 API 获取联系人...")
        api_contacts = get_all_contacts()
        if api_contacts:
            contact_display_name_map = api_contacts

    # 3. 获取今天的群消息
    raw_messages = get_today_messages(group_id)
    if raw_messages is None: # 表示API请求失败
        print("获取消息失败，程序退出。")
        return
    if not raw_messages: # 表示今天没有消息
        print("今天没有新的媒体消息需要处理。")
        return

    # 4. 预处理消息，添加 sender_display_name，并转换为 MessageInfo 对象
    processed_messages = []
    for msg in raw_messages:
        sender_username = msg.get("senderUsername")
        display_name = contact_display_name_map.get(sender_username, sender_username)
        processed_messages.append(MessageInfo(msg, display_name))

    # 5. 对所有消息按时间排序，确保匹配逻辑的正确性
    processed_messages.sort(key=lambda x: x.create_time)

    # 6. 匹配媒体消息和说明文字
    print("正在匹配媒体消息和说明文字...")
    matched_results = match_media_with_text(processed_messages)
    
    if not matched_results:
        print("没有匹配到任何需要保存的媒体消息。")
        return

    # 7. 保存媒体和说明
    print("正在保存匹配到的媒体文件和说明...")
    save_media_and_description(matched_results)

    print("--- 微信群媒体整理工具运行完毕 ---")

if __name__ == "__main__":
    main()