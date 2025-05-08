import os
import logging
import io
import base64
from typing import Union, List, Tuple, Optional, Dict, Any

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("face_recognition")

# 延遲導入處理依賴
def load_cv2():
    try:
        import cv2
        return cv2
    except ImportError as e:
        logger.error(f"無法導入OpenCV: {str(e)}")
        raise

def load_np():
    try:
        import numpy as np
        return np
    except ImportError as e:
        logger.error(f"無法導入NumPy: {str(e)}")
        raise

def load_pil():
    try:
        from PIL import Image
        return Image
    except ImportError as e:
        logger.error(f"無法導入PIL: {str(e)}")
        raise

# 全局變量
face_cascade = None
known_faces = {}  # 格式: {employee_id: face_encoding}

def initialize_face_detector():
    """初始化臉部檢測器"""
    global face_cascade
    
    try:
        cv2 = load_cv2()
        
        # 初始化臉部檢測器
        face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if not os.path.exists(face_cascade_path):
            logger.warning(f"找不到預設的臉部檢測器路徑: {face_cascade_path}")
            # 嘗試找其他路徑
            alt_path = os.path.join(os.path.dirname(__file__), "haarcascade_frontalface_default.xml")
            if os.path.exists(alt_path):
                face_cascade_path = alt_path
                logger.info(f"使用替代臉部檢測器路徑: {alt_path}")
            else:
                # 嘗試下載
                import requests
                cascade_url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
                local_path = os.path.join(os.path.dirname(__file__), "models")
                os.makedirs(local_path, exist_ok=True)
                local_path = os.path.join(local_path, "haarcascade_frontalface_default.xml")
                
                try:
                    response = requests.get(cascade_url, stream=True)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                    face_cascade_path = local_path
                    logger.info(f"成功下載臉部檢測器到: {local_path}")
                except Exception as e:
                    logger.error(f"無法下載臉部檢測器: {str(e)}")
                    return False
        
        # 創建臉部檢測器
        face_cascade = cv2.CascadeClassifier(face_cascade_path)
        if face_cascade.empty():
            logger.error("臉部檢測器初始化失敗，檢測器為空")
            return False
            
        logger.info("臉部檢測器初始化成功")
        return True
            
    except Exception as e:
        logger.error(f"初始化臉部檢測器失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def detect_faces(image):
    """檢測圖像中的所有人臉"""
    global face_cascade
    
    # 初始化檢測器（如果尚未初始化）
    if face_cascade is None:
        if not initialize_face_detector():
            return []
    
    try:
        cv2 = load_cv2()
        np = load_np()
        
        # 轉換為灰度圖像
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 檢測人臉 - 調整參數提高敏感度
        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.05,  # 降低scaleFactor(原為1.1)使檢測更敏感
            minNeighbors=3,    # 降低minNeighbors(原為5)減少誤判
            minSize=(20, 20)   # 降低最小尺寸(原為30,30)以檢測更小的人臉
        )
        logger.info(f"檢測到的人臉數量: {len(faces)}")
        # 將結果轉換為列表
        if isinstance(faces, np.ndarray) and len(faces) > 0:
            return faces.tolist()
        return []
        
    except Exception as e:
        logger.error(f"人臉檢測失敗: {str(e)}")
        return []

def compare_faces(known_encoding, face_encoding, tolerance=0.8):
    """比較兩個人臉編碼，判斷是否為同一人"""
    try:
        np = load_np()
        
        if known_encoding is None or face_encoding is None:
            return False
            
        # 計算歐式距離
        if isinstance(known_encoding, list):
            known_encoding = np.array(known_encoding)
        if isinstance(face_encoding, list):
            face_encoding = np.array(face_encoding)
            
        dist = np.linalg.norm(known_encoding - face_encoding)
        return dist <= tolerance
        
    except Exception as e:
        logger.error(f"人臉比較失敗: {str(e)}")
        return False

def encode_face(image, face_location=None):
    """對人臉進行編碼"""
    try:
        cv2 = load_cv2()
        np = load_np()
        
        # 如果未提供人臉位置，嘗試檢測
        if face_location is None:
            faces = detect_faces(image)
            if not faces:
                logger.warning("未檢測到人臉，無法進行編碼")
                return None
            face_location = faces[0]  # 使用第一個檢測到的人臉
        
        # 提取人臉區域 - 加入邊界擴展以獲取更多面部特徵
        x, y, w, h = face_location
        # 增加邊界範圍 (10%)
        padding_x = int(w * 0.1)
        padding_y = int(h * 0.1)
        # 確保不超出圖像邊界
        start_x = max(0, x - padding_x)
        start_y = max(0, y - padding_y)
        end_x = min(image.shape[1], x + w + padding_x)
        end_y = min(image.shape[0], y + h + padding_y)
        
        face_image = image[start_y:end_y, start_x:end_x]
        
        # 調整大小為統一尺寸
        face_image = cv2.resize(face_image, (160, 160))
        
        # 進行圖像預處理 - 增強對比度
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        
        # 使用高斯模糊減少噪音
        blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
        
        # 使用簡單的特徵提取方法（HOG特徵）
        win_size = (160, 160)
        block_size = (16, 16)
        block_stride = (8, 8)
        cell_size = (8, 8)
        nbins = 9
        hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, nbins)
        encoding = hog.compute(blurred)
        
        # 歸一化特徵向量
        if np.linalg.norm(encoding) > 0:
            encoding = encoding / np.linalg.norm(encoding)
        
        return encoding.flatten().tolist()
        
    except Exception as e:
        logger.error(f"人臉編碼失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def register_face(employee_id, image_data):
    """註冊員工的人臉"""
    global known_faces
    
    try:
        # 解析圖像數據
        image = decode_image(image_data)
        if image is None:
            return {"success": False, "error": "無法解碼圖像數據"}
            
        # 檢測人臉
        faces = detect_faces(image)
        if not faces:
            return {"success": False, "error": "未檢測到人臉"}
            
        # 使用第一個檢測到的人臉
        face_location = faces[0]
        
        # 編碼人臉
        face_encoding = encode_face(image, face_location)
        if face_encoding is None:
            return {"success": False, "error": "人臉編碼失敗"}
            
        # 保存編碼
        known_faces[str(employee_id)] = face_encoding
        
        logger.info(f"成功註冊員工 ID {employee_id} 的人臉")
        return {"success": True, "message": "人臉註冊成功"}
        
    except Exception as e:
        logger.error(f"人臉註冊失敗: {str(e)}")
        return {"success": False, "error": str(e)}

def load_faces_from_db(db_face_data):
    """從資料庫加載已註冊的人臉數據"""
    global known_faces
    known_faces.update(db_face_data)
    logger.info(f"已從資料庫載入 {len(db_face_data)} 筆人臉資料")
    
def recognize_face(image_data, db_face_data=None):
    """識別圖像中的人臉，返回匹配的員工ID
    
    參數:
        image_data: 圖像數據
        db_face_data: 可選，直接從數據庫傳入的人臉編碼字典
    """
    global known_faces
    
    # 如果直接傳入了數據庫數據，先更新內存中的數據
    if db_face_data and isinstance(db_face_data, dict):
        known_faces.update(db_face_data)
        logger.info(f"從參數加載了 {len(db_face_data)} 筆人臉數據")
    
    if not known_faces:
        logger.warning("沒有註冊的人臉數據，無法識別")
        return None
    
    logger.info(f"當前已加載 {len(known_faces)} 筆人臉數據")
        
    try:
        # 解析圖像數據
        image = decode_image(image_data)
        if image is None:
            logger.error("無法解碼圖像數據")
            return None
            
        # 檢測人臉
        faces = detect_faces(image)
        if not faces:
            logger.error("未檢測到人臉")
            return None
            
        # 使用第一個檢測到的人臉
        face_location = faces[0]
        logger.info(f"檢測到人臉位置: {face_location}")
        
        # 編碼人臉
        face_encoding = encode_face(image, face_location)
        if face_encoding is None:
            logger.error("人臉編碼失敗")
            return None
            
        # 與已知人臉比較
        matches = []
        match_scores = {}
        
        # 打印出所有已知人臉的IDs，便於調試
        logger.info(f"正在與以下員工ID比對: {list(known_faces.keys())}")
        
        for employee_id, known_encoding in known_faces.items():
            # 計算歐式距離以獲取匹配分數
            try:
                np = load_np()
                if isinstance(known_encoding, list):
                    known_encoding = np.array(known_encoding)
                if isinstance(face_encoding, list):
                    face_encoding = np.array(face_encoding)
                    
                distance = np.linalg.norm(known_encoding - face_encoding)
                match_scores[employee_id] = distance
                
                # 提高容錯度 - 從0.6提高到0.8
                if distance <= 0.8:
                    matches.append(employee_id)
                    logger.info(f"匹配到員工ID: {employee_id}, 距離分數: {distance:.4f}")
            except Exception as e:
                logger.error(f"比較人臉時出錯 (ID: {employee_id}): {e}")
        
        # 記錄所有比對結果供診斷
        for emp_id, score in sorted(match_scores.items(), key=lambda x: x[1]):
            logger.info(f"員工ID {emp_id} 的匹配分數: {score:.4f}")
            
            # 添加醒目的終端輸出，將相似度轉換為百分比
            similarity_percent = max(0, (1 - score) * 100)  # 距離越小，相似度越高
            print(f"【人臉相似度】員工ID {emp_id} - 相似度: {similarity_percent:.2f}%")
        
        if matches:
            # 如果有多個匹配，選擇距離最小的一個
            if len(matches) > 1:
                best_match = min(matches, key=lambda emp_id: match_scores[emp_id])
                logger.info(f"多個匹配結果，選擇最佳匹配: {best_match}, 距離: {match_scores[best_match]:.4f}")
                
                # 添加醒目的最佳匹配終端輸出
                best_similarity = max(0, (1 - match_scores[best_match]) * 100)
                print(f"【最佳匹配】員工ID {best_match} - 相似度: {best_similarity:.2f}%")
            else:
                best_match = matches[0]
                logger.info(f"成功匹配到員工ID: {best_match}, 距離: {match_scores[best_match]:.4f}")
                
                # 添加醒目的匹配終端輸出
                matched_similarity = max(0, (1 - match_scores[best_match]) * 100)
                print(f"【成功匹配】員工ID {best_match} - 相似度: {matched_similarity:.2f}%")
            
            # 直接返回員工ID而非dict
            return best_match
        else:
            # 如果沒有匹配，也顯示最相似的結果
            if match_scores:
                closest_id = min(match_scores.keys(), key=lambda k: match_scores[k])
                closest_score = match_scores[closest_id]
                logger.warning(f"未找到匹配的人臉，最接近的是員工ID {closest_id}，分數: {closest_score:.4f}")
            else:
                logger.warning("未找到任何匹配分數")
            return None
            
    except Exception as e:
        logger.error(f"人臉識別失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def decode_image(image_data):
    """將圖像數據解碼為OpenCV格式"""
    try:
        cv2 = load_cv2()
        np = load_np()
        
        # 如果是numpy數組，直接返回
        if isinstance(image_data, np.ndarray):
            if len(image_data.shape) == 3 and image_data.shape[2] in [3, 4]:  # RGB或RGBA圖像
                return image_data
            else:
                logger.error(f"不支持的numpy圖像格式，形狀: {image_data.shape}")
                return None
        
        if isinstance(image_data, str):
            # 處理base64編碼的圖像
            if image_data.startswith("data:image"):
                # 分離MIME和數據部分
                image_data = image_data.split(",")[1]
                
            # 解碼base64
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
        elif isinstance(image_data, bytes):
            # 直接處理二進制數據
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
        else:
            logger.error(f"不支持的圖像數據格式: {type(image_data)}")
            return None
            
        return image
        
    except Exception as e:
        logger.error(f"圖像解碼失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# 初始化人臉檢測器
initialize_face_detector() 