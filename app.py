from flask import Flask, jsonify, request
import requests
import json
import time
import urllib3
import jwt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import json_format
import r1_pb2 
import binascii
import my_pb2
import output_pb2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

FREEFIRE_VERSION = "OB53"
FRIEND_URL = "https://clientbp.ggpolarbear.com/GetFriend"

FRIEND_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
FRIEND_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

# -----------------------------
# AES Configuration for Login
# -----------------------------
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

def encrypt_message(data_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(data_bytes, AES.block_size))

def encrypt_friend_payload(hex_data: str) -> bytes:
    raw = bytes.fromhex(hex_data)
    cipher = AES.new(FRIEND_KEY, AES.MODE_CBC, FRIEND_IV)
    return cipher.encrypt(pad(raw, AES.block_size))

# -----------------------------
# JWT Token Generation Functions (من الكود السابق)
# -----------------------------
def get_token_from_uid_password(uid, password):
    """Get JWT token using UID and password"""
    try:
        oauth_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        payload = {
            'uid': uid,
            'password': password,
            'response_type': "token",
            'client_type': "2",
            'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            'client_id': "100067"
        }
        
        headers = {
            'User-Agent': "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip"
        }

        oauth_response = requests.post(oauth_url, data=payload, headers=headers, timeout=10, verify=False)
        oauth_response.raise_for_status()
        
        oauth_data = oauth_response.json()
        
        if 'access_token' not in oauth_data:
            return None, "OAuth response missing access_token"

        access_token = oauth_data['access_token']
        open_id = oauth_data.get('open_id', '')
        
        # Try platforms with the obtained credentials
        platforms = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        
        for platform_type in platforms:
            result = try_platform_login(open_id, access_token, platform_type)
            if result and 'token' in result:
                return result['token'], None
        
        return None, "Login successful but JWT generation failed on all platforms"

    except requests.RequestException as e:
        return None, f"OAuth request failed: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

def try_platform_login(open_id, access_token, platform_type):
    """Try login for a specific platform"""
    try:
        game_data = my_pb2.GameData()
        game_data.timestamp = "2024-12-05 18:15:32"
        game_data.game_name = "free fire"
        game_data.game_version = 1
        game_data.version_code = "1.108.3"
        game_data.os_info = "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)"
        game_data.device_type = "Handheld"
        game_data.network_provider = "Verizon Wireless"
        game_data.connection_type = "WIFI"
        game_data.screen_width = 1280
        game_data.screen_height = 960
        game_data.dpi = "240"
        game_data.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
        game_data.total_ram = 5951
        game_data.gpu_name = "Adreno (TM) 640"
        game_data.gpu_version = "OpenGL ES 3.0"
        game_data.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
        game_data.ip_address = "172.190.111.97"
        game_data.language = "en"
        game_data.open_id = open_id
        game_data.access_token = access_token
        game_data.platform_type = platform_type
        game_data.field_99 = str(platform_type)
        game_data.field_100 = str(platform_type)

        serialized_data = game_data.SerializeToString()
        encrypted_data = encrypt_message(serialized_data)
        hex_encrypted_data = binascii.hexlify(encrypted_data).decode('utf-8')

        url = "https://loginbp.ggpolarbear.com/MajorLogin"
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/octet-stream",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53"
        }
        
        edata = bytes.fromhex(hex_encrypted_data)

        response = requests.post(url, data=edata, headers=headers, timeout=10, verify=False)
        response.raise_for_status()

        if response.status_code == 200:
            example_msg = output_pb2.Garena_420()
            example_msg.ParseFromString(response.content)
            data_dict = {field.name: getattr(example_msg, field.name)
                         for field in example_msg.DESCRIPTOR.fields
                         if field.name not in ["binary", "binary_data", "Garena420"]}

            if data_dict and "token" in data_dict:
                token_value = data_dict["token"]
                return {
                    "token": token_value
                }
        
        return None

    except Exception:
        return None

def decode_author_uid(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("account_id") or decoded.get("sub")
    except:
        return None

# -----------------------------
# Friend List Functions
# -----------------------------
def api_response(friends_list, my_info):
    return jsonify({
        "friends_count": len(friends_list),
        "friends_list": friends_list,
        "my_info": my_info,
        "Credit": "xAMINE.py",
        "status": "success",
        "timestamp": int(time.time())
    })

def get_friend_list(token):
    """Get friend list using JWT token"""
    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": FREEFIRE_VERSION,
        "Content-Type": "application/octet-stream",
        "User-Agent": "Dalvik/2.1.0 (Linux; Android 11)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip"
    }

    payload_hex = "080110011001"
    encrypted_payload = encrypt_friend_payload(payload_hex)

    r = requests.post(
        FRIEND_URL,
        headers=headers,
        data=encrypted_payload,
        timeout=15,
        verify=False
    )

    if r.status_code != 200:
        return None, f"Free Fire server error: {r.status_code}"

    pb = r1_pb2.Friends()
    pb.ParseFromString(r.content)

    parsed = json.loads(
        json_format.MessageToJson(pb)
    )

    raw_list = []
    for entry in parsed.get("field1", []):
        uid = str(entry.get("ID", "unknown"))
        name = "unknown"

        for k, v in entry.items():
            if isinstance(v, str) and k != "ID":
                name = v
                break

        raw_list.append({
            "uid": uid,
            "name": name
        })

    if not raw_list:
        return [], None

    my_info = raw_list[-1] 
    friends_list = raw_list[:-1] 
    
    return friends_list, my_info

# -----------------------------
# API Routes - المدعومة الآن
# -----------------------------
@app.route("/")
def home():
    return jsonify({
        "usage": {
            "via_token": "/<JWT_TOKEN>",
            "via_uid_password": "/friend_list?uid=<UID>&password=<PASSWORD>"
        },
        "status": "online"
    })

# الطريقة القديمة -直接用 JWT في المسار
@app.route("/<path:jwt>", methods=["GET"])
def friend_list_by_path(jwt):
    if not jwt or jwt.count(".") != 2:
        return jsonify({
            "status": "error",
            "message": "Invalid JWT token format"
        }), 400

    friends_list, my_info = get_friend_list(jwt)
    
    if friends_list is None:
        return jsonify({
            "status": "error",
            "message": my_info if my_info else "Failed to get friend list"
        }), 500

    return api_response(friends_list, my_info)

# الطريقة الجديدة - باستخدام UID و Password
@app.route("/friend_list", methods=["GET"])
def friend_list_by_credentials():
    """Get friend list using UID and password"""
    uid = request.args.get('uid')
    password = request.args.get('password')
    
    if not uid or not password:
        return jsonify({
            "status": "error",
            "message": "Missing uid or password. Use: /friend_list?uid=XXX&password=YYY"
        }), 400
    
    # الحصول على التوكن من UID وكلمة المرور
    token, error = get_token_from_uid_password(uid, password)
    
    if error:
        return jsonify({
            "status": "error",
            "message": f"Authentication failed: {error}"
        }), 401
    
    # التحقق من صحة التوكن
    author_uid = decode_author_uid(token)
    if not author_uid:
        return jsonify({
            "status": "error",
            "message": "Generated token is invalid"
        }), 401
    
    # جلب قائمة الأصدقاء
    friends_list, my_info = get_friend_list(token)
    
    if friends_list is None:
        return jsonify({
            "status": "error",
            "message": my_info if my_info else "Failed to get friend list"
        }), 500
    
    # إضافة معلومات الحساب المستخدم
    if my_info:
        my_info["logged_in_uid"] = author_uid
    
    return api_response(friends_list, my_info)

# Route للتحقق من صحة التوكن فقط
@app.route("/verify", methods=["GET"])
def verify_token():
    """Verify if a token is valid"""
    token = request.args.get('token')
    uid = request.args.get('uid')
    password = request.args.get('password')
    
    if not token and uid and password:
        token, error = get_token_from_uid_password(uid, password)
        if error:
            return jsonify({"status": "error", "message": error}), 401
    
    if not token:
        return jsonify({"status": "error", "message": "Token required"}), 400
    
    author_uid = decode_author_uid(token)
    if author_uid:
        return jsonify({
            "status": "success",
            "uid": author_uid,
            "token_valid": True
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Invalid token"
        }), 401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)