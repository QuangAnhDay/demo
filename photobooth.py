import sys
import os
import cv2
import time
import subprocess
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QMessageBox, QFrame, QGridLayout, QStackedWidget)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon

# ==========================================
# CẤU HÌNH (CONFIGURATION)
# ==========================================
WINDOW_TITLE = "Photobooth Cảm Ứng"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
CAMERA_INDEX = 0
FIRST_PHOTO_DELAY = 10  # Giây cho ảnh đầu tiên
BETWEEN_PHOTO_DELAY = 7  # Giây giữa các ảnh
PHOTOS_TO_TAKE = 10
TEMPLATE_DIR = "templates"
OUTPUT_DIR = "output"

# ==========================================
# HÀM HỖ TRỢ (HELPER FUNCTIONS)
# ==========================================

def ensure_directories():
    """Tạo các thư mục cần thiết."""
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        create_sample_templates()
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def create_sample_templates():
    """Tạo các template mẫu."""
    width, height = 1280, 720
    
    # Template 1: Khung đỏ đơn giản
    img = np.zeros((height, width, 4), dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (width, height), (0, 0, 255, 255), 40)
    cv2.putText(img, "PHOTOBOOTH", (width//2 - 200, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255, 255), 4)
    img[80:height-40, 40:width-40] = [0, 0, 0, 0]
    cv2.imwrite(os.path.join(TEMPLATE_DIR, "frame_red.png"), img)
    
    # Template 2: Khung xanh
    img2 = np.zeros((height, width, 4), dtype=np.uint8)
    cv2.rectangle(img2, (0, 0), (width, height), (255, 100, 0, 255), 40)
    cv2.putText(img2, "MEMORIES", (width//2 - 150, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255, 255), 4)
    img2[80:height-40, 40:width-40] = [0, 0, 0, 0]
    cv2.imwrite(os.path.join(TEMPLATE_DIR, "frame_blue.png"), img2)

def overlay_images(background, foreground):
    """Ghép ảnh foreground (có alpha) lên background."""
    bg_h, bg_w = background.shape[:2]
    fg_h, fg_w = foreground.shape[:2]

    if (bg_w, bg_h) != (fg_w, fg_h):
        foreground = cv2.resize(foreground, (bg_w, bg_h))

    if foreground.shape[2] < 4:
        return background
    
    alpha = foreground[:, :, 3] / 255.0
    output = np.zeros_like(background)
    
    for c in range(0, 3):
        output[:, :, c] = (foreground[:, :, c] * alpha + 
                           background[:, :, c] * (1.0 - alpha))
    
    return output

def convert_cv_qt(cv_img):
    """Chuyển đổi ảnh OpenCV sang QPixmap."""
    if cv_img is None:
        return QPixmap()
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb_image.shape
    bytes_per_line = ch * w
    qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return QPixmap.fromImage(qt_format)

def check_printer_available():
    """Kiểm tra xem có máy in nào được kết nối không (Windows)."""
    if os.name != 'nt':
        return False, "Chỉ hỗ trợ Windows"
    
    try:
        # Dùng PowerShell để lấy danh sách máy in
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Printer | Select-Object -ExpandProperty Name'],
            capture_output=True, text=True, timeout=5
        )
        printers = result.stdout.strip().split('\n')
        printers = [p.strip() for p in printers if p.strip()]
        
        if printers:
            return True, printers[0]  # Trả về máy in đầu tiên
        else:
            return False, "Không tìm thấy máy in"
    except Exception as e:
        return False, str(e)

# ==========================================
# GIAO DIỆN CHÍNH (MAIN GUI)
# ==========================================

class PhotoboothApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QLabel { 
                color: white; 
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
            }
            QLabel#TitleLabel {
                font-size: 32px;
                font-weight: bold;
                color: #eaf0f6;
            }
            QLabel#CountdownLabel {
                font-size: 120px;
                font-weight: bold;
                color: #ffd700;
            }
            QLabel#InfoLabel {
                font-size: 24px;
                color: #a8dadc;
            }
            QPushButton {
                background-color: #e94560;
                color: white;
                border: none;
                border-radius: 15px;
                padding: 20px 40px;
                font-size: 22px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-height: 60px;
            }
            QPushButton:hover { background-color: #ff6b6b; }
            QPushButton:pressed { background-color: #c73e5a; }
            QPushButton:disabled { background-color: #4a4a6a; color: #8a8a9a; }
            QPushButton#GreenBtn { background-color: #06d6a0; }
            QPushButton#GreenBtn:hover { background-color: #00f5d4; }
            QPushButton#OrangeBtn { background-color: #fb8500; }
            QPushButton#OrangeBtn:hover { background-color: #ffb703; }
            QPushButton#BlueBtn { background-color: #4361ee; }
            QPushButton#BlueBtn:hover { background-color: #4cc9f0; }
            QPushButton#FrameBtn {
                background-color: #16213e;
                border: 3px solid #0f3460;
                border-radius: 20px;
                padding: 30px;
                min-height: 120px;
            }
            QPushButton#FrameBtn:hover { 
                background-color: #0f3460; 
                border-color: #e94560;
            }
            QPushButton#FrameBtn:checked { 
                background-color: #06d6a0; 
                border-color: #00f5d4;
            }
            QScrollArea { 
                border: none; 
                background-color: transparent; 
            }
            QWidget#PhotoCard {
                background-color: #16213e;
                border-radius: 10px;
                border: 2px solid #0f3460;
            }
            QWidget#PhotoCard:hover {
                border-color: #e94560;
            }
        """)

        # --- STATE MANAGEMENT ---
        self.state = "START"  # START, CAPTURING, FRAME_SELECT, PHOTO_SELECT, TEMPLATE_SELECT, CONFIRM, PRINTING
        self.captured_photos = []
        self.selected_frame_count = 0  # 1, 2, hoặc 4
        self.selected_photo_indices = []
        self.collage_image = None
        self.merged_image = None
        self.current_frame = None
        self.countdown_val = 0
        
        # --- CAMERA ---
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # --- MAIN LAYOUT ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # --- STACKED WIDGET cho các màn hình ---
        self.stacked = QStackedWidget()
        self.main_layout.addWidget(self.stacked)

        # Tạo các màn hình
        self.create_start_screen()       # Index 0
        self.create_capture_screen()     # Index 1
        self.create_frame_select_screen() # Index 2
        self.create_photo_select_screen() # Index 3
        self.create_template_select_screen() # Index 4
        self.create_confirm_screen()     # Index 5

        # --- TIMER ---
        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.update_camera_frame)
        self.camera_timer.start(30)

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.countdown_tick)

        # Load templates
        self.templates = self.load_templates()

    # ==========================================
    # TẠO CÁC MÀN HÌNH
    # ==========================================

    def create_start_screen(self):
        """Màn hình bắt đầu."""
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(40)

        title = QLabel("📸 PHOTOBOOTH")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Chạm vào nút bên dưới để bắt đầu chụp ảnh!")
        subtitle.setObjectName("InfoLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        self.btn_start = QPushButton("BẮT ĐẦU CHỤP")
        self.btn_start.setObjectName("GreenBtn")
        self.btn_start.setFixedSize(400, 100)
        self.btn_start.clicked.connect(self.start_capture_session)
        layout.addWidget(self.btn_start, alignment=Qt.AlignCenter)

        self.stacked.addWidget(screen)

    def create_capture_screen(self):
        """Màn hình chụp ảnh với camera live."""
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(10)

        # Camera view
        self.camera_label = QLabel("Đang khởi động camera...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("""
            background-color: #000; 
            border: 4px solid #e94560; 
            border-radius: 15px;
        """)
        self.camera_label.setMinimumSize(900, 500)
        layout.addWidget(self.camera_label, stretch=4)

        # Info bar
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        
        self.photo_count_label = QLabel("Ảnh: 0/10")
        self.photo_count_label.setObjectName("InfoLabel")
        info_layout.addWidget(self.photo_count_label)
        
        self.countdown_label = QLabel("")
        self.countdown_label.setObjectName("CountdownLabel")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.countdown_label, stretch=1)
        
        self.status_label = QLabel("Chuẩn bị...")
        self.status_label.setObjectName("InfoLabel")
        self.status_label.setAlignment(Qt.AlignRight)
        info_layout.addWidget(self.status_label)
        
        layout.addWidget(info_widget)

        self.stacked.addWidget(screen)

    def create_frame_select_screen(self):
        """Màn hình chọn kiểu khung (1, 2, hoặc 4 ảnh)."""
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)

        title = QLabel("CHỌN KIỂU KHUNG ẢNH")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Frame options
        options_layout = QHBoxLayout()
        options_layout.setSpacing(40)

        self.frame_buttons = []
        frame_options = [
            ("1 ẢNH", 1, "🖼️"),
            ("2 ẢNH", 2, "🖼️🖼️"),
            ("4 ẢNH", 4, "🖼️🖼️\n🖼️🖼️")
        ]

        for label, count, icon in frame_options:
            btn = QPushButton(f"{icon}\n\n{label}")
            btn.setObjectName("FrameBtn")
            btn.setCheckable(True)
            btn.setFixedSize(250, 200)
            btn.clicked.connect(lambda checked, c=count, b=btn: self.select_frame_type(c, b))
            options_layout.addWidget(btn)
            self.frame_buttons.append(btn)

        layout.addLayout(options_layout)

        # Confirm button
        self.btn_confirm_frame = QPushButton("TIẾP TỤC CHỌN ẢNH")
        self.btn_confirm_frame.setObjectName("GreenBtn")
        self.btn_confirm_frame.setEnabled(False)
        self.btn_confirm_frame.clicked.connect(self.go_to_photo_select)
        layout.addWidget(self.btn_confirm_frame, alignment=Qt.AlignCenter)

        self.stacked.addWidget(screen)

    def create_photo_select_screen(self):
        """Màn hình chọn ảnh từ 10 ảnh đã chụp."""
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(15)

        self.photo_select_title = QLabel("CHỌN 1 ẢNH")
        self.photo_select_title.setObjectName("TitleLabel")
        self.photo_select_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.photo_select_title)

        # Scroll area for photo grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent;")
        
        self.photo_grid_widget = QWidget()
        self.photo_grid_layout = QGridLayout(self.photo_grid_widget)
        self.photo_grid_layout.setSpacing(15)
        scroll.setWidget(self.photo_grid_widget)
        layout.addWidget(scroll, stretch=1)

        # Confirm button
        self.btn_confirm_photos = QPushButton("XÁC NHẬN CHỌN ẢNH")
        self.btn_confirm_photos.setObjectName("GreenBtn")
        self.btn_confirm_photos.setEnabled(False)
        self.btn_confirm_photos.clicked.connect(self.confirm_photo_selection)
        layout.addWidget(self.btn_confirm_photos, alignment=Qt.AlignCenter)

        self.stacked.addWidget(screen)

    def create_template_select_screen(self):
        """Màn hình chọn template/khung viền."""
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(15)

        title = QLabel("CHỌN KHUNG VIỀN")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Preview
        self.template_preview_label = QLabel()
        self.template_preview_label.setAlignment(Qt.AlignCenter)
        self.template_preview_label.setStyleSheet("""
            background-color: #000;
            border: 3px solid #4361ee;
            border-radius: 10px;
        """)
        self.template_preview_label.setMinimumSize(700, 400)
        layout.addWidget(self.template_preview_label, stretch=1)

        # Template options (horizontal scroll)
        template_scroll = QScrollArea()
        template_scroll.setWidgetResizable(True)
        template_scroll.setFixedHeight(150)
        template_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        self.template_btn_widget = QWidget()
        self.template_btn_layout = QHBoxLayout(self.template_btn_widget)
        template_scroll.setWidget(self.template_btn_widget)
        layout.addWidget(template_scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_no_template = QPushButton("KHÔNG DÙNG KHUNG")
        self.btn_no_template.setObjectName("OrangeBtn")
        self.btn_no_template.clicked.connect(self.use_no_template)
        btn_layout.addWidget(self.btn_no_template)
        
        self.btn_confirm_template = QPushButton("XÁC NHẬN")
        self.btn_confirm_template.setObjectName("GreenBtn")
        self.btn_confirm_template.clicked.connect(self.go_to_confirm)
        btn_layout.addWidget(self.btn_confirm_template)
        
        layout.addLayout(btn_layout)

        self.stacked.addWidget(screen)

    def create_confirm_screen(self):
        """Màn hình xác nhận cuối cùng trước khi in."""
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        title = QLabel("BẠN CÓ ĐỒNG Ý VỚI MẪU NÀY KHÔNG?")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Final preview
        self.final_preview_label = QLabel()
        self.final_preview_label.setAlignment(Qt.AlignCenter)
        self.final_preview_label.setStyleSheet("""
            background-color: #000;
            border: 4px solid #06d6a0;
            border-radius: 15px;
        """)
        self.final_preview_label.setMinimumSize(800, 450)
        layout.addWidget(self.final_preview_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        
        self.btn_reject = QPushButton("CHỤP LẠI TỪ ĐẦU")
        self.btn_reject.setObjectName("OrangeBtn")
        self.btn_reject.setFixedSize(300, 80)
        self.btn_reject.clicked.connect(self.reset_all)
        btn_layout.addWidget(self.btn_reject)
        
        self.btn_accept = QPushButton("ĐỒNG Ý - IN ẢNH")
        self.btn_accept.setObjectName("GreenBtn")
        self.btn_accept.setFixedSize(300, 80)
        self.btn_accept.clicked.connect(self.accept_and_print)
        btn_layout.addWidget(self.btn_accept)
        
        layout.addLayout(btn_layout)

        self.stacked.addWidget(screen)

    # ==========================================
    # LOGIC ĐIỀU KHIỂN
    # ==========================================

    def load_templates(self):
        """Load danh sách templates."""
        templates = []
        if os.path.exists(TEMPLATE_DIR):
            for f in os.listdir(TEMPLATE_DIR):
                if f.lower().endswith('.png'):
                    templates.append(os.path.join(TEMPLATE_DIR, f))
        return templates

    def update_camera_frame(self):
        """Cập nhật frame từ camera."""
        if self.state == "CAPTURING":
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                self.current_frame = frame.copy()
                
                # Hiển thị lên camera label
                qt_img = convert_cv_qt(frame)
                scaled = qt_img.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.camera_label.setPixmap(scaled)

    def start_capture_session(self):
        """Bắt đầu phiên chụp ảnh."""
        self.state = "CAPTURING"
        self.captured_photos = []
        self.selected_photo_indices = []
        self.selected_frame_count = 0
        
        # Chuyển sang màn hình chụp
        self.stacked.setCurrentIndex(1)
        
        # Bắt đầu đếm ngược cho ảnh đầu tiên (10 giây)
        self.countdown_val = FIRST_PHOTO_DELAY
        self.photo_count_label.setText(f"Ảnh: 0/{PHOTOS_TO_TAKE}")
        self.status_label.setText("Chuẩn bị tạo dáng!")
        self.countdown_label.setText(str(self.countdown_val))
        
        self.countdown_timer.start(1000)

    def countdown_tick(self):
        """Xử lý mỗi giây đếm ngược."""
        self.countdown_val -= 1
        
        if self.countdown_val > 0:
            self.countdown_label.setText(str(self.countdown_val))
        else:
            # Chụp ảnh!
            self.countdown_label.setText("📸")
            self.capture_photo()

    def capture_photo(self):
        """Chụp một ảnh."""
        if self.current_frame is not None:
            self.captured_photos.append(self.current_frame.copy())
            photo_num = len(self.captured_photos)
            self.photo_count_label.setText(f"Ảnh: {photo_num}/{PHOTOS_TO_TAKE}")
            
            if photo_num < PHOTOS_TO_TAKE:
                # Còn ảnh cần chụp, đặt countdown 7 giây
                self.countdown_val = BETWEEN_PHOTO_DELAY
                self.countdown_label.setText(str(self.countdown_val))
                self.status_label.setText(f"Đã chụp ảnh {photo_num}! Tiếp tục...")
            else:
                # Đã chụp đủ 10 ảnh
                self.countdown_timer.stop()
                self.countdown_label.setText("✓")
                self.status_label.setText("Hoàn thành!")
                
                # Chuyển sang chọn kiểu khung sau 1 giây
                QTimer.singleShot(1000, self.go_to_frame_select)

    def go_to_frame_select(self):
        """Chuyển sang màn hình chọn kiểu khung."""
        self.state = "FRAME_SELECT"
        
        # Reset trạng thái các nút
        for btn in self.frame_buttons:
            btn.setChecked(False)
        self.btn_confirm_frame.setEnabled(False)
        self.selected_frame_count = 0
        
        self.stacked.setCurrentIndex(2)

    def select_frame_type(self, count, button):
        """Xử lý khi chọn kiểu khung."""
        # Bỏ check các nút khác
        for btn in self.frame_buttons:
            if btn != button:
                btn.setChecked(False)
        
        self.selected_frame_count = count
        self.btn_confirm_frame.setEnabled(True)

    def go_to_photo_select(self):
        """Chuyển sang màn hình chọn ảnh."""
        self.state = "PHOTO_SELECT"
        self.selected_photo_indices = []
        
        # Cập nhật title
        self.photo_select_title.setText(f"CHỌN {self.selected_frame_count} ẢNH")
        
        # Clear grid cũ
        for i in reversed(range(self.photo_grid_layout.count())):
            self.photo_grid_layout.itemAt(i).widget().deleteLater()
        
        # Tạo grid ảnh (2 hàng x 5 cột)
        self.photo_buttons = []
        for idx, img in enumerate(self.captured_photos):
            container = QWidget()
            container.setObjectName("PhotoCard")
            container.setFixedSize(200, 150)
            
            layout = QVBoxLayout(container)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setSpacing(5)
            
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(180, 100)
            
            thumb = cv2.resize(img, (180, 100))
            btn.setIcon(QIcon(convert_cv_qt(thumb)))
            btn.setIconSize(QSize(180, 100))
            btn.setStyleSheet("border: 2px solid transparent; border-radius: 5px;")
            btn.clicked.connect(lambda checked, i=idx, b=btn: self.toggle_photo(i, b))
            
            layout.addWidget(btn)
            
            lbl = QLabel(f"Ảnh {idx + 1}")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 14px;")
            layout.addWidget(lbl)
            
            row = idx // 5
            col = idx % 5
            self.photo_grid_layout.addWidget(container, row, col)
            self.photo_buttons.append(btn)
        
        self.btn_confirm_photos.setEnabled(False)
        self.stacked.setCurrentIndex(3)

    def toggle_photo(self, index, button):
        """Xử lý chọn/bỏ chọn ảnh."""
        if index in self.selected_photo_indices:
            self.selected_photo_indices.remove(index)
            button.setStyleSheet("border: 2px solid transparent; border-radius: 5px;")
        else:
            if len(self.selected_photo_indices) >= self.selected_frame_count:
                # Đã chọn đủ, bỏ chọn ảnh này
                button.setChecked(False)
                QMessageBox.information(self, "Thông báo", 
                    f"Bạn chỉ được chọn {self.selected_frame_count} ảnh!")
                return
            
            self.selected_photo_indices.append(index)
            button.setStyleSheet("border: 4px solid #06d6a0; border-radius: 5px;")
        
        # Enable/disable confirm button
        self.btn_confirm_photos.setEnabled(
            len(self.selected_photo_indices) == self.selected_frame_count
        )

    def confirm_photo_selection(self):
        """Xác nhận chọn ảnh và tạo collage."""
        selected_imgs = [self.captured_photos[i] for i in sorted(self.selected_photo_indices)]
        self.collage_image = self.create_collage(selected_imgs)
        self.merged_image = self.collage_image.copy()
        
        self.go_to_template_select()

    def create_collage(self, images):
        """Tạo collage từ các ảnh đã chọn."""
        canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
        count = len(images)
        
        if count == 1:
            canvas = cv2.resize(images[0], (1280, 720))
        elif count == 2:
            for i, img in enumerate(images):
                h, w = img.shape[:2]
                center_x = w // 2
                start_x = max(0, center_x - 320)
                end_x = min(w, start_x + 640)
                cropped = img[0:min(h, 720), start_x:end_x]
                cropped = cv2.resize(cropped, (640, 720))
                canvas[0:720, i*640:(i+1)*640] = cropped
        elif count == 4:
            for i, img in enumerate(images):
                resized = cv2.resize(img, (640, 360))
                row = i // 2
                col = i % 2
                canvas[row*360:(row+1)*360, col*640:(col+1)*640] = resized
        
        return canvas

    def go_to_template_select(self):
        """Chuyển sang màn hình chọn template."""
        self.state = "TEMPLATE_SELECT"
        
        # Hiển thị preview ban đầu
        self.update_template_preview()
        
        # Populate template buttons
        for i in reversed(range(self.template_btn_layout.count())):
            self.template_btn_layout.itemAt(i).widget().deleteLater()
        
        for path in self.templates:
            btn = QPushButton()
            btn.setFixedSize(120, 100)
            pix = QPixmap(path).scaled(100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(100, 80))
            btn.setStyleSheet("""
                background-color: #16213e; 
                border: 2px solid #0f3460;
                border-radius: 10px;
            """)
            btn.clicked.connect(lambda checked, p=path: self.apply_template(p))
            self.template_btn_layout.addWidget(btn)
        
        self.stacked.setCurrentIndex(4)

    def update_template_preview(self):
        """Cập nhật preview."""
        if self.merged_image is not None:
            qt_img = convert_cv_qt(self.merged_image)
            scaled = qt_img.scaled(
                self.template_preview_label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.template_preview_label.setPixmap(scaled)

    def apply_template(self, template_path):
        """Áp dụng template lên collage."""
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is not None and self.collage_image is not None:
            self.merged_image = overlay_images(self.collage_image.copy(), template)
            self.update_template_preview()

    def use_no_template(self):
        """Không sử dụng template."""
        self.merged_image = self.collage_image.copy()
        self.go_to_confirm()

    def go_to_confirm(self):
        """Chuyển sang màn hình xác nhận."""
        self.state = "CONFIRM"
        
        # Hiển thị preview cuối
        if self.merged_image is not None:
            qt_img = convert_cv_qt(self.merged_image)
            scaled = qt_img.scaled(
                self.final_preview_label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.final_preview_label.setPixmap(scaled)
        
        self.stacked.setCurrentIndex(5)

    def accept_and_print(self):
        """Đồng ý và tiến hành in ảnh."""
        if self.merged_image is None:
            return
        
        # Kiểm tra máy in
        printer_ok, printer_info = check_printer_available()
        
        if not printer_ok:
            QMessageBox.warning(
                self, 
                "⚠️ MÁY IN CHƯA ĐƯỢC KẾT NỐI",
                f"Không thể in ảnh!\n\nLý do: {printer_info}\n\n"
                "Vui lòng kiểm tra kết nối máy in và thử lại."
            )
            return
        
        # Lưu file
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"photo_{timestamp}.jpg"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        cv2.imwrite(filepath, self.merged_image)
        
        # In ảnh
        try:
            os.startfile(filepath, "print")
            QMessageBox.information(
                self,
                "✅ ĐANG IN ẢNH",
                f"Ảnh đã được gửi đến máy in: {printer_info}\n\n"
                f"File đã lưu: {filename}\n\n"
                "Vui lòng chờ trong giây lát..."
            )
            
            # Reset về màn hình bắt đầu sau khi in
            QTimer.singleShot(3000, self.reset_all)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ LỖI IN ẢNH",
                f"Không thể in ảnh: {str(e)}"
            )

    def reset_all(self):
        """Reset toàn bộ về trạng thái ban đầu."""
        self.state = "START"
        self.captured_photos = []
        self.selected_photo_indices = []
        self.selected_frame_count = 0
        self.collage_image = None
        self.merged_image = None
        
        # Về màn hình bắt đầu
        self.stacked.setCurrentIndex(0)

    def closeEvent(self, event):
        """Cleanup khi đóng app."""
        self.camera_timer.stop()
        self.countdown_timer.stop()
        self.cap.release()
        event.accept()


if __name__ == "__main__":
    ensure_directories()
    app = QApplication(sys.argv)
    
    # Set font mặc định
    font = QFont("Segoe UI", 12)
    app.setFont(font)
    
    window = PhotoboothApp()
    window.show()
    sys.exit(app.exec_())
