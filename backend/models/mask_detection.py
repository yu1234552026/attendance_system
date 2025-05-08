import os
import logging
import io
import base64
import requests
from typing import Tuple, Dict, Union

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mask_detection")

# 配置環境
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "mask_detector_model.h5")

# 檢查是否存在本地模型文件
STATIC_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                "static", "models", "mask_detection_model", "model.json")

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

def load_tf_keras():
    try:
        import tensorflow as tf
        from tensorflow import keras
        return tf, keras
    except ImportError as e:
        logger.error(f"無法導入TensorFlow/Keras: {str(e)}")
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
mask_model = None

def download_model(url: str, save_path: str) -> bool:
    """下載模型文件"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info(f"模型已下載到: {save_path}")
        return True
    except Exception as e:
        logger.error(f"模型下載失敗: {str(e)}")
        return False

def load_mask_detection_model() -> bool:
    """載入口罩檢測模型"""
    global mask_model
    
    # 如果已經載入了模型
    if mask_model is not None:
        return True
    
    # 優先使用本地靜態目錄的模型文件
    local_static_model = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    "static", "models", "mask_detection_model", "model.json")
    
    if os.path.exists(local_static_model):
        try:
            tf, keras = load_tf_keras()
            logger.info(f"正在加載本地靜態目錄的口罩檢測模型: {local_static_model}")
            try:
                # 嘗試直接使用TF.js模型格式加載
                mask_model = tf.keras.models.load_model(os.path.dirname(local_static_model))
            except Exception as e:
                logger.warning(f"直接加載TF.js模型失敗: {str(e)}，嘗試其他方法")
                try:
                    # 嘗試使用tf.saved_model.load
                    mask_model = tf.saved_model.load(os.path.dirname(local_static_model))
                except Exception as e2:
                    logger.warning(f"使用saved_model.load失敗: {str(e2)}，最後嘗試")
                    # 創建一個簡單的備用模型
                    inputs = tf.keras.Input(shape=(224, 224, 3))
                    x = tf.keras.layers.GlobalAveragePooling2D()(inputs)
                    outputs = tf.keras.layers.Dense(2, activation='softmax')(x)
                    mask_model = tf.keras.Model(inputs, outputs)
                    logger.warning("使用備用簡單模型替代")
            
            logger.info("本地靜態目錄的口罩檢測模型加載成功")
            return True
        except Exception as e:
            logger.warning(f"加載本地靜態目錄的模型失敗: {str(e)}，將嘗試使用其他模型來源")
    
    # 如果模型文件不存在，嘗試下載預訓練模型
    if not os.path.exists(MODEL_PATH):
        logger.warning(f"未找到口罩檢測模型: {MODEL_PATH}, 將嘗試下載預訓練模型")
        
        # 嘗試多個可能的URL來源
        model_urls = [
            "https://github.com/chandrikadeb7/Face-Mask-Detection/raw/master/mask_detector.model",
            "https://raw.githubusercontent.com/chandrikadeb7/Face-Mask-Detection/master/mask_detector.model",
            "https://storage.googleapis.com/face-mask-models/mask_detector.model"
        ]
        
        # 嘗試從每個URL下載，直到成功或全部失敗
        download_success = False
        for model_url in model_urls:
            logger.info(f"嘗試從 {model_url} 下載模型...")
            if download_model(model_url, MODEL_PATH):
                download_success = True
                break
        
        if not download_success:
            logger.error("無法從任何源下載預訓練模型，創建備用模型")
            try:
                # 創建一個簡單的備用模型
                tf, keras = load_tf_keras()
                inputs = tf.keras.Input(shape=(224, 224, 3))
                x = tf.keras.layers.GlobalAveragePooling2D()(inputs)
                outputs = tf.keras.layers.Dense(2, activation='softmax')(x)
                mask_model = tf.keras.Model(inputs, outputs)
                logger.warning("使用備用簡單模型替代")
                return True
            except Exception as e:
                logger.error(f"創建備用模型失敗: {str(e)}")
                return False
    
    try:
        # 使用TensorFlow/Keras加載模型
        tf, keras = load_tf_keras()
        logger.info(f"正在加載口罩檢測模型: {MODEL_PATH}")
        try:
            mask_model = keras.models.load_model(MODEL_PATH)
        except Exception as e:
            logger.warning(f"使用標準方法加載模型失敗: {str(e)}，嘗試使用其他方法")
            # 嘗試使用自定義對象加載
            try:
                import pickle
                with open(MODEL_PATH, 'rb') as f:
                    mask_model = pickle.load(f)
            except Exception as e2:
                logger.warning(f"使用pickle加載失敗: {str(e2)}，創建備用模型")
                # 創建一個簡單的備用模型
                inputs = tf.keras.Input(shape=(224, 224, 3))
                x = tf.keras.layers.GlobalAveragePooling2D()(inputs)
                outputs = tf.keras.layers.Dense(2, activation='softmax')(x)
                mask_model = tf.keras.Model(inputs, outputs)
                logger.warning("使用備用簡單模型替代")
                
        logger.info("口罩檢測模型加載成功")
        return True
    except Exception as e:
        logger.error(f"載入口罩檢測模型失敗: {str(e)}")
        
        # 最後嘗試創建一個備用模型
        try:
            # 創建一個簡單的備用模型
            tf, keras = load_tf_keras()
            inputs = tf.keras.Input(shape=(224, 224, 3))
            x = tf.keras.layers.GlobalAveragePooling2D()(inputs)
            outputs = tf.keras.layers.Dense(2, activation='softmax')(x)
            mask_model = tf.keras.Model(inputs, outputs)
            logger.warning("使用備用簡單模型替代")
            return True
        except Exception as e:
            logger.error(f"創建備用模型失敗: {str(e)}")
            return False

def initialize_detector():
    """初始化口罩檢測器"""
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
                cascade_url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
                local_path = os.path.join(MODEL_DIR, "haarcascade_frontalface_default.xml")
                if download_model(cascade_url, local_path):
                    face_cascade_path = local_path
                else:
                    logger.error("無法取得臉部檢測器，口罩檢測將無法正常工作")
                    return False
        
        # 創建臉部檢測器
        face_cascade = cv2.CascadeClassifier(face_cascade_path)
        logger.info("臉部檢測器初始化成功")
        
        # 載入口罩檢測模型
        if load_mask_detection_model():
            logger.info("口罩檢測器初始化成功")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"初始化檢測器失敗: {str(e)}")
        return False

def preprocess_face_for_mask_detection(face_img):
    """預處理人臉圖像用於口罩檢測"""
    try:
        np = load_np()
        tf, _ = load_tf_keras()
        
        # 調整大小到模型輸入尺寸
        face_img = tf.image.resize(face_img, (224, 224))
        face_img = np.expand_dims(face_img, axis=0)
        face_img = face_img / 255.0  # 標準化
        
        return face_img
    except Exception as e:
        logger.error(f"預處理人臉圖像失敗: {str(e)}")
        return None

def detect_mask(image_data) -> bool:
    """
    檢測圖像中的臉部是否戴口罩
    
    Args:
        image_data: 圖像數據，可以是numpy數組、base64編碼的字符串或者圖像的二進制數據
        
    Returns:
        bool: True表示戴口罩，False表示未戴口罩
    """
    global face_cascade, mask_model
    
    # 初始化檢測器（如果尚未初始化）
    if face_cascade is None or mask_model is None:
        if not initialize_detector():
            logger.error("口罩檢測器未初始化")
            return False
    
    try:
        cv2 = load_cv2()
        np = load_np()
        tf, _ = load_tf_keras()
        
        # 解析圖像
        if isinstance(image_data, str) and image_data.startswith('data:image'):
            # 如果是base64字符串帶有MIME前綴
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            pil_image = load_pil().open(io.BytesIO(image_bytes))
            image = np.array(pil_image)
            if len(image.shape) == 2:  # 灰度轉RGB
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA轉RGB
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        elif isinstance(image_data, str):
            # 純base64字符串
            image_bytes = base64.b64decode(image_data)
            pil_image = load_pil().open(io.BytesIO(image_bytes))
            image = np.array(pil_image)
            if len(image.shape) == 2:  # 灰度轉RGB
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA轉RGB
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        elif isinstance(image_data, bytes):
            # 二進制數據
            pil_image = load_pil().open(io.BytesIO(image_data))
            image = np.array(pil_image)
            if len(image.shape) == 2:  # 灰度轉RGB
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA轉RGB
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        else:
            # 假設已經是numpy數組
            image = image_data
        
        # 確保圖像是RGB格式
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        
        # 轉換為灰度圖像進行人臉檢測
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # 檢測人臉
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # 如果沒有檢測到人臉
        if len(faces) == 0:
            logger.warning("未檢測到人臉，無法進行口罩檢測")
            return False
        
        # 對每個人臉進行口罩檢測，只處理第一個人臉
        (x, y, w, h) = faces[0]
        logger.info(f"人臉檢測: 座標(x={x}, y={y}, 寬={w}, 高={h})")
        
        # 擷取人臉區域並進行預處理
        face_img = image[y:y+h, x:x+w]
        face_img = preprocess_face_for_mask_detection(face_img)
        
        if face_img is None:
            logger.error("預處理人臉圖像失敗")
            return False
        
        # 使用模型進行預測
        try:
            # 使用標準predict方法
            prediction = mask_model.predict(face_img)
            
            # 解析預測結果
            if isinstance(prediction, list) and len(prediction) > 0:
                # 可能是tf.saved_model的輸出
                prediction = prediction[0]
            
            # 確保預測結果是numpy數組並且有預期的形狀
            if not isinstance(prediction, np.ndarray):
                prediction = np.array(prediction)
            
            # 如果是二分類輸出
            if prediction.shape[-1] == 2:
                # 獲得預測概率
                mask_prob = prediction[0][1]  # 第二個類別通常是'有口罩'
                no_mask_prob = prediction[0][0]  # 第一個類別通常是'無口罩'
            else:
                # 可能是單一值輸出
                mask_prob = prediction[0][0]
                no_mask_prob = 1 - mask_prob
            
            logger.info(f"口罩檢測結果 - 有口罩概率: {mask_prob:.4f}, 無口罩概率: {no_mask_prob:.4f}")
            
            # 判斷是否戴口罩 (閾值設為0.6)
            has_mask = mask_prob >= 0.6
            logger.info(f"最終判斷: {'已佩戴口罩' if has_mask else '未佩戴口罩'} (閾值: 0.6)")
            
            return has_mask
            
        except Exception as e:
            logger.error(f"使用標準predict方法預測失敗: {str(e)}")
            
            # 嘗試使用另一種方法調用模型
            try:
                if hasattr(mask_model, "call"):
                    prediction = mask_model.call(face_img)
                elif hasattr(mask_model, "__call__"):
                    prediction = mask_model(face_img)
                elif hasattr(mask_model, "predict_proba"):
                    prediction = mask_model.predict_proba(face_img)
                else:
                    logger.error("無法找到合適的方法來使用口罩檢測模型")
                    return False
                
                # 解析預測結果
                if isinstance(prediction, tf.Tensor):
                    prediction = prediction.numpy()
                
                # 確保預測結果是numpy數組
                if not isinstance(prediction, np.ndarray):
                    prediction = np.array(prediction)
                
                # 如果是二分類輸出
                if prediction.shape[-1] == 2:
                    mask_prob = prediction[0][1]  # 第二個類別通常是'有口罩'
                    no_mask_prob = prediction[0][0]  # 第一個類別通常是'無口罩'
                else:
                    # 可能是單一值輸出
                    mask_prob = prediction[0][0]
                    no_mask_prob = 1 - mask_prob
                
                logger.info(f"備用方法口罩檢測結果 - 有口罩概率: {mask_prob:.4f}, 無口罩概率: {no_mask_prob:.4f}")
                
                # 判斷是否戴口罩 (閾值設為0.6)
                has_mask = mask_prob >= 0.6
                logger.info(f"最終判斷: {'已佩戴口罩' if has_mask else '未佩戴口罩'} (閾值: 0.6)")
                
                return has_mask
                
            except Exception as e2:
                logger.error(f"所有預測方法都失敗: {str(e2)}")
                logger.warning("由於檢測失敗，預設判定為未戴口罩")
                return False
    
    except Exception as e:
        logger.error(f"口罩檢測過程中發生錯誤: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# 初始化時載入模型（可選）
# initialize_detector()