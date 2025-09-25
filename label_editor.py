""" MAIN """


import os
import json
import math 
# from functools import partial 

from PyQt5.QtCore import (
    Qt, QPointF, QRectF, QSize, QObject, pyqtSignal
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QPen, QColor, QTransform, QFont, QBrush, QPainterPath
)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsItemGroup, QVBoxLayout, QHBoxLayout, QComboBox, QSpinBox,
    QSlider, QMessageBox, QInputDialog 
)



class ResizableRotatedBoxItem(QGraphicsItem):
     # Corner identifiers for handles
    TopLeft, TopRight, BottomLeft, BottomRight = range(4)

    def __init__(self, w=100.0, h=100.0, angle=0.0, label="", classes=None, parent=None):
        super().__init__(parent)
        self.w = w
        self.h = h
        self.angle = angle # Item rotation is handled by setRotation
        self.setRotation(angle)
        self.label = label
        self.classes = classes or []
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True) # Required for hoverMoveEvent to work

        # Resize and Rotate handles properties
        self.handle_size = 8.0
        self.handles = {} 
        self._dragging_handle = None

        self._rotating = False
        self._rotate_start_scene = None # Scene position when rotation started
        self._angle_start = 0.0
        self._last_move_scene = None # Scene position for resizing drag

        self.updateHandlesPos()

    def updateHandlesPos(self):
        """Recompute corner handles (QRectF) in local item coordinates."""
        s = self.handle_size
        halfw = self.w / 2
        halfh = self.h / 2
        # Define handles as small squares around the corners of the unrotated box
        self.handles = {
            ResizableRotatedBoxItem.TopLeft: QRectF(-halfw - s/2, -halfh - s/2, s, s),
            ResizableRotatedBoxItem.TopRight: QRectF(halfw - s/2, -halfh - s/2, s, s),
            ResizableRotatedBoxItem.BottomLeft: QRectF(-halfw - s/2, halfh - s/2, s, s),
            ResizableRotatedBoxItem.BottomRight: QRectF(halfw - s/2, halfh - s/2, s, s),
        }
        
    def getRotationHandleRect(self):
        """Get the QRectF for the rotation handle (in local item coords)."""
        offset_y = -self.h/2 - 20
        size = self.handle_size
        return QRectF(-size/2, offset_y - size/2, size, size)

    def boundingRect(self):
        # We need to compute the bounding box that encompasses the rotated box AND the handles.
        # This is complex in a rotated item, so we use a safe, slightly padded unrotated rect
        # and include the rotation handle area. The scene will take care of rotation.
        pad = self.handle_size + 25 # Extra padding to ensure rotation handle is included
        return QRectF(-self.w/2 - pad, -self.h/2 - pad, self.w + pad * 2, self.h + pad * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()

        # Draw main rectangle (item coordinates, implicitly rotated by QGraphicsItem)
        rect = QRectF(-self.w/2, -self.h/2, self.w, self.h)
        pen = QPen(QColor("red") if self.isSelected() else QColor("green"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect)

        # Draw corner handles if selected
        if self.isSelected():
            painter.setBrush(QColor(200, 200, 200))
            painter.setPen(Qt.NoPen)
            for _, hrect in self.handles.items():
                painter.drawRect(hrect)

            # Draw rotation handle
            painter.setBrush(QColor(150, 150, 255))
            painter.drawRect(self.getRotationHandleRect())
            
            # Draw label text near top-left
            painter.setPen(QPen(Qt.black, 1))
            painter.drawText(rect.topLeft() + QPointF(4, -4), self.label)

        painter.restore()

    def shape(self):
        # Define the clickable shape for the item (main rect + handles)
        path = QPainterPath()
        rect = QRectF(-self.w / 2, -self.h / 2, self.w, self.h)
        path.addRect(rect)
        if self.isSelected():
            for r in self.handles.values():
                path.addRect(r)
            path.addRect(self.getRotationHandleRect())
        return path
    
    def hoverMoveEvent(self, event):
        pos = event.pos()
        cursor = Qt.ArrowCursor
        
        # Check rotation handle
        if self.getRotationHandleRect().contains(pos):
             # CrossCursor is often used for rotation handles
            cursor = Qt.CrossCursor
        else:
            # Check resize handles
            for _, rect in self.handles.items():
                if rect.contains(pos):
                    cursor = Qt.SizeAllCursor # Generic resize cursor
                    break

        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        pos = event.pos()
        self._last_move_scene = event.scenePos()

        # 1. Check for rotation handle
        if self.getRotationHandleRect().contains(pos):
            self._rotating = True
            self._rotate_start_scene = event.scenePos()
            self._angle_start = self.rotation()
            event.accept()
            return
        
        # 2. Check for resizing handles
        for corner, hrect in self.handles.items():
            if hrect.contains(pos):
                self._dragging_handle = corner
                event.accept()
                return

        # 3. Default behavior (movement, selection)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        current_scene_pos = event.scenePos()
        
        if self._rotating:
            center_scene = self.mapToScene(QPointF(0, 0))
            v0 = self._rotate_start_scene - center_scene
            v1 = current_scene_pos - center_scene
            
            # Calculate angle change
            angle0 = math.degrees(math.atan2(v0.y(), v0.x()))
            angle1 = math.degrees(math.atan2(v1.y(), v1.x()))
            da = angle1 - angle0
            
            self.angle = self._angle_start + da 
            
            self.setRotation(self.angle)
            event.accept()
            return
        elif self._dragging_handle is not None:
            # Resizing logic (crucial part)
            delta_scene = current_scene_pos - self._last_move_scene
            
            # Map scene delta to unrotated item local coordinates
            # This is the vector component change along the object's width/height axes
            inv_rot_transform = QTransform().rotate(-self.rotation())
            # map(delta) - map(QPointF(0,0)) gives the vector difference in the new coordinate system
            delta_local = inv_rot_transform.map(delta_scene) - inv_rot_transform.map(QPointF(0, 0))
            dx = delta_local.x()
            dy = delta_local.y()
            
            # Resizing and repositioning based on the corner
            new_w, new_h = self.w, self.h
            pos_offset = QPointF(0, 0) # Item movement offset 
            
            # The logic below accounts for the center moving in the direction opposite to the resized edge.
            if self._dragging_handle in (ResizableRotatedBoxItem.TopLeft, ResizableRotatedBoxItem.BottomLeft):
                new_w -= dx
                pos_offset += QPointF(dx / 2, 0)
            if self._dragging_handle in (ResizableRotatedBoxItem.TopRight, ResizableRotatedBoxItem.BottomRight):
                new_w += dx
                pos_offset += QPointF(dx / 2, 0)
            if self._dragging_handle in (ResizableRotatedBoxItem.TopLeft, ResizableRotatedBoxItem.TopRight):
                new_h -= dy
                pos_offset += QPointF(0, dy / 2)
            if self._dragging_handle in (ResizableRotatedBoxItem.BottomLeft, ResizableRotatedBoxItem.BottomRight):
                new_h += dy
                pos_offset += QPointF(0, dy / 2)
            
            self.prepareGeometryChange()

            # Enforce minimum size
            self.w = max(new_w, self.handle_size * 2)
            self.h = max(new_h, self.handle_size * 2)
            
            # Move the center of the box by mapping the calculated local offset back to scene coordinates
            # The map(offset) - map(QPointF(0,0)) transforms the local offset (pos_offset) into the rotated
            # scene position change
            rot_transform = QTransform().rotate(self.rotation())
            scene_offset = rot_transform.map(pos_offset) - rot_transform.map(QPointF(0, 0))
            self.setPos(self.pos() + scene_offset)

            self.updateHandlesPos()
            self.update()
            self._last_move_scene = current_scene_pos # Important to update for next move
            event.accept()
            return
            
        super().mouseMoveEvent(event) 

    def mouseReleaseEvent(self, event):
        self._dragging_handle = None
        self._rotating = False
        self.setCursor(Qt.ArrowCursor) 
        self._last_move_scene = None
        super().mouseReleaseEvent(event)

    def setLabel(self, label: str):
        self.label = label
        self.update()

    def to_dict(self):
        # convert to a serializable dict
        center = self.pos() # The item's position is its center in scene coords

        # Start with the item's current state
        w_out = self.w
        h_out = self.h
        angle_out = self.angle
        
        # --- DATA NORMALIZATION FOR +/- 90 DEGREE RANGE ---
        # 1. Normalize current angle to -180 to 180 range
        
        # norm_angle = angle_out - 90 
        # print(norm_angle) 
        
        # # 2. Adjust angle and swap W/H if outside +/- 90
        # if norm_angle > 90:
        #     angle_out = norm_angle - 180
        #     w_out, h_out = h_out, w_out # Swap W and H
        # elif norm_angle < -90:
        #     angle_out = norm_angle + 180
        #     w_out, h_out = h_out, w_out # Swap W and H
        # else:
        #     angle_out = norm_angle # Keep normalized angle
        
        norm_angle = angle_out % 360
        if norm_angle > 180:
            norm_angle -= 360
        elif norm_angle <= -180:
            norm_angle += 360
            
        angle_out = norm_angle 
        # print(angle_out) 
        
        # 2. Iteratively constrain the angle to the (-90, 90] range by swapping W/H.
        # Repeat until the angle is within the target range.
        
        # If angle is > 90 (e.g., 100 degrees), it's equivalent to -80 degrees with W/H swapped.
        while angle_out > 90:
            angle_out -= 180
            # w_out, h_out = h_out, w_out
            
        # If angle is <= -90 (e.g., -100 degrees), it's equivalent to 80 degrees with W/H swapped.
        while angle_out <= -90:
            angle_out += 180
            # w_out, h_out = h_out, w_out

        return {
            "cx": center.x(),
            "cy": center.y(),
            "w": w_out, #self.w,
            "h": h_out, #self.h,
            "angle": angle_out, #self.angle, # Use self.angle (which is set by setRotation)
            "label": self.label
        }

    @classmethod
    def from_dict(cls, d: dict, classes=None):
        obj = cls(w=d["w"], h=d["h"], angle=d.get("angle", 0.0),
                    label=d.get("label", ""), classes=classes) 
        
        obj.setPos(QPointF(d["cx"], d["cy"])) 
        
        # Set the item's internal angle and rotation directly from the saved value
        # This will be in the (-90, 90] range
        obj.angle = d.get("angle", 0.0)
        obj.setRotation(obj.angle)

        # Rotation is set in __init__
        obj.updateHandlesPos()
        return obj

# class RotatedBoxItem(QGraphicsItem):
#     """
#     A QGraphicsItem representing a rotated bounding box with a label.
#     The box is defined by its center, width, height, and rotation angle.
#     """

#     def __init__(self, center: QPointF, w: float, h: float, angle: float = 0.0, label: str = "", classes=None, parent=None):
#         super().__init__(parent)
#         self.center = center
#         self.w = w
#         self.h = h
#         self.angle = angle  # degrees
#         self.label = label
#         self.classes = classes or []
#         self.setFlags(
#             QGraphicsItem.ItemIsSelectable |
#             QGraphicsItem.ItemIsMovable |
#             QGraphicsItem.ItemSendsGeometryChanges
#         )
#         self.handle_size = 8  # size of the rotation handle square
#         self.handle_offset = QPointF(0, - (self.h/2 + 20))  # offset from center for handle in unrotated orientation

#     def boundingRect(self):
#         # Return the bounding box of this item (in item-local coords)
#         pad = self.handle_size
#         return QRectF(-self.w/2 - pad, -self.h/2 - pad - 20, self.w + pad*2, self.h + pad*2 + 20)

#     def paint(self, painter: QPainter, option, widget=None):
#         # Draw the box: a rectangle plus a rotation handle
#         painter.save()

#         # draw rotated rectangle
#         rect = QRectF(-self.w/2, -self.h/2, self.w, self.h)
#         pen = QPen(QColor("red") if self.isSelected() else QColor("green"))
#         pen.setWidth(2)
#         painter.setPen(pen)
#         painter.drawRect(rect)

#         # draw the rotation handle as a small square
#         # compute its position (in the rotated coordinates)
#         handle_pos = self.handle_offset
#         painter.drawRect(QRectF(handle_pos.x() - self.handle_size/2,
#                                 handle_pos.y() - self.handle_size/2,
#                                 self.handle_size, self.handle_size))

#         # draw label text at top-left corner
#         painter.setPen(Qt.black)
#         painter.drawText(rect.topLeft() + QPointF(4, -4), self.label)

#         painter.restore()

#     def shape(self):
#         # You can refine this to include handle region, etc.
#         path = super().shape()
#         return path

#     def itemChange(self, change, value):
#         if change == QGraphicsItem.ItemPositionChange:
#             # keep within parent boundary if needed
#             return value
#         return super().itemChange(change, value)

#     def mousePressEvent(self, event):
#         # If the user clicked near the handle, we initiate a rotation drag
#         pos = event.pos()
#         # Transform pos into unrotated coordinates
#         inv = QTransform().rotate(-self.angle)
#         local = inv.map(pos)
#         # If within handle square
#         if QRectF(self.handle_offset.x() - self.handle_size/2,
#                   self.handle_offset.y() - self.handle_size/2,
#                   self.handle_size, self.handle_size).contains(local):
#             self._rotating = True
#             self._rotate_start = event.scenePos()
#             self._angle_start = self.angle
#             event.accept()
#             return
#         else:
#             self._rotating = False
#         super().mousePressEvent(event)

#     def mouseMoveEvent(self, event):
#         if getattr(self, "_rotating", False):
#             # compute angle change
#             center_scene = self.mapToScene(QPointF(0,0))
#             v0 = self._rotate_start - center_scene
#             v1 = event.scenePos() - center_scene
#             # angle between v0 and v1
#             angle0 = math.degrees(math.atan2(v0.y(), v0.x()))
#             angle1 = math.degrees(math.atan2(v1.y(), v1.x()))
#             da = angle1 - angle0
#             self.angle = self._angle_start + da
#             self.setRotation(self.angle)
#             event.accept()
#             return
#         super().mouseMoveEvent(event)

#     def mouseReleaseEvent(self, event):
#         self._rotating = False
#         super().mouseReleaseEvent(event)

#     def setLabel(self, label: str):
#         self.label = label
#         self.update()

#     def to_dict(self):
#         # Save in a dict form
#         return {
#             "cx": self.center.x(),
#             "cy": self.center.y(),
#             "w": self.w,
#             "h": self.h,
#             "angle": self.angle,
#             "label": self.label
#         }

#     @classmethod
#     def from_dict(cls, d: dict, classes=None):
#         return cls(
#             center=QPointF(d["cx"], d["cy"]),
#             w=d["w"],
#             h=d["h"],
#             angle=d.get("angle", 0.0),
#             label=d.get("label", ""),
#             classes=classes
#         )

class ImageCanvas(QGraphicsView):
    """
    The view that shows the image and the bounding boxes.
    """ 
    boxCreated = pyqtSignal(ResizableRotatedBoxItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self._pixmap_item = None
        self.classes = []
        self.image_width = 0
        self.image_height = 0

        self._drawing = False
        self._box_start_scene = None
        self._current_box = None
        self.drawing_mode = False  # Controlled via 'W' key
        self.image_rect = QRectF()  # Will store image bounds

    def load_image(self, img_path: str):
        pix = QPixmap(img_path)
        self.image_width = pix.width()
        self.image_height = pix.height()
        self.scene.clear()
        self._pixmap_item = self.scene.addPixmap(pix)
        
        # 🐛 FIX: Convert QRect to QRectF
        # pix.rect() returns a QRect, but setSceneRect expects a QRectF
        self.setSceneRect(QRectF(pix.rect())) 
        
        self.image_rect = QRectF(0, 0, pix.width(), pix.height())  # Image bounds
    
    def wheelEvent(self, event):
        # Check if the Ctrl key is pressed
        if event.modifiers() & Qt.ControlModifier:
            # Determine the direction of scroll
            delta = event.angleDelta().y()
            
            # The current scale factor is derived from the transform matrix
            current_scale = self.transform().m11()
            
            # Zoom factor
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor
            
            if delta > 0:
                # Scroll up/forward -> Zoom in
                scale_factor = zoom_in_factor
            elif delta < 0:
                # Scroll down/backward -> Zoom out
                scale_factor = zoom_out_factor
            else:
                return # No vertical scroll
                
            new_scale = current_scale * scale_factor
            
            # Optional: Limit the zoom range (e.g., between 0.1x and 5.0x)
            new_scale = max(0.1, min(5.0, new_scale))

            # Apply the new scale centered at the current mouse position (recommended for graphics views)
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.setTransform(QTransform().scale(new_scale, new_scale))
            self.setTransformationAnchor(QGraphicsView.AnchorViewCenter) # Reset anchor to view center

            # Update the slider value if you want it to be in sync
            # Note: This might be slightly inaccurate due to the floating point nature of scale
            window = self.parent() # Assuming parent is AnnotatorWindow
            if window and hasattr(window, 'slider_zoom'):
                window.slider_zoom.setValue(int(new_scale * 100))
                
            event.accept()
        else:
            # Fallback to default behavior (e.g., vertical scrolling if the view is scrollable)
            super().wheelEvent(event) 
    
    def mousePressEvent(self, event):
        pos = self.mapToScene(event.pos())

        if self.drawing_mode and event.button() == Qt.LeftButton:
            if not self.image_rect.contains(pos):
                return
            self._drawing = True
            self._start_pos = pos
            self._current_box = ResizableRotatedBoxItem()
            self._current_box.setPos(pos)
            self.scene.addItem(self._current_box)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drawing and self._current_box:
            pos = self.mapToScene(event.pos())
            pos.setX(min(max(pos.x(), 0), self.image_rect.width()))
            pos.setY(min(max(pos.y(), 0), self.image_rect.height()))
            dx = pos.x() - self._start_pos.x()
            dy = pos.y() - self._start_pos.y() 

            self._current_box.prepareGeometryChange() 

            self._current_box.w = abs(dx)
            self._current_box.h = abs(dy)
            cx = (self._start_pos.x() + pos.x()) / 2
            cy = (self._start_pos.y() + pos.y()) / 2
            self._current_box.setPos(QPointF(cx, cy))
            self._current_box.updateHandlesPos()
            self._current_box.update()
        else:
            super().mouseMoveEvent(event) 

    def mouseReleaseEvent(self, event):
        if self._drawing and self._current_box:
            # Finalize the box only if it has a non-zero size
            if self._current_box.w > 10 and self._current_box.h > 10:
                self.boxCreated.emit(self._current_box)
            else:
                self.scene.removeItem(self._current_box) # Remove tiny box
                
            self._drawing = False
            self._current_box = None
        else:
            super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        # Forward Left/Right arrow keys to the parent window (AnnotatorWindow)
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_Right:
            # Tell the event it's NOT accepted, so it propagates up to the parent
            event.ignore() 
            # Or, more explicitly, call the parent's function if needed, 
            # but ignoring it is the standard Qt way to propagate.
            return 
        
        super().keyPressEvent(event)
    
    def load_annotations(self, ann_path: str):
        if not os.path.exists(ann_path):
            return
        with open(ann_path, "r") as f:
            data = json.load(f)
        for bd in data.get("boxes", []):
            box = ResizableRotatedBoxItem.from_dict(bd, classes=self.classes)
            self.scene.addItem(box)

    def save_annotations(self, ann_path: str):
        boxes = []
        for item in self.scene.items():
            if isinstance(item, ResizableRotatedBoxItem):
                boxes.append(item.to_dict())
        with open(ann_path, "w") as f:
            json.dump({"boxes": boxes}, f, indent=2)

class AnnotatorWindow(QWidget):
    def __init__(self):
        super().__init__() 
        self.setFocusPolicy(Qt.StrongFocus)

        self.canvas = ImageCanvas()
        self.btn_open = QPushButton("Open Image Folder")
        self.btn_prev = QPushButton("Prev")
        self.btn_next = QPushButton("Next")
        self.btn_add_class = QPushButton("Add Class")
        self.combo_labels = QComboBox()
        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(10, 400)
        self.slider_zoom.setValue(60)

        h1 = QHBoxLayout()
        h1.addWidget(self.btn_open)
        h1.addWidget(self.btn_prev)
        h1.addWidget(self.btn_next)
        h1.addWidget(self.btn_add_class)
        h1.addWidget(QLabel("Label:"))
        h1.addWidget(self.combo_labels)
        h1.addWidget(QLabel("Zoom:"))
        h1.addWidget(self.slider_zoom)

        v = QVBoxLayout()
        v.addLayout(h1)
        v.addWidget(self.canvas)
        self.setLayout(v)

        # connect
        self.btn_open.clicked.connect(self.open_folder)
        self.btn_prev.clicked.connect(self.prev_image)
        self.btn_next.clicked.connect(self.next_image)
        self.btn_add_class.clicked.connect(self.on_add_class)
        self.slider_zoom.valueChanged.connect(self.on_zoom_changed)
        self.combo_labels.currentIndexChanged.connect(self.on_label_changed)

        self.canvas.boxCreated.connect(self.on_box_created)

        self.image_paths = []
        self.current_idx = -1
        self.classes = []
        self.undo_stack = []  # store (action, object) tuples

        self.load_classes() 
        self.update_title() 
    
    def update_title(self):
        # Get the status of drawing mode
        mode_status = 'ON' if self.canvas.drawing_mode else 'OFF'
        
        # Get the current image name
        image_name = ""
        if self.current_idx >= 0 and self.current_idx < len(self.image_paths):
            image_name = os.path.basename(self.image_paths[self.current_idx])

        # Set the full title
        self.setWindowTitle(f"Image Labeler | {image_name} | Draw Mode: {mode_status}")
    
    def load_classes(self):
        if os.path.exists("classes.txt"):
            with open("classes.txt", "r") as f:
                self.classes = [ln.strip() for ln in f if ln.strip()]
        else:
            self.classes = []
        self.combo_labels.clear()
        self.combo_labels.addItems(self.classes)
        self.canvas.classes = self.classes

    def open_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if not d:
            return
        exts = {".jpg", ".jpeg", ".png", ".bmp"}
        self.image_paths = [os.path.join(d, fn)
                             for fn in os.listdir(d)
                             if os.path.splitext(fn)[1].lower() in exts]
        self.image_paths.sort()
        if self.image_paths:
            self.current_idx = 0
            self.load_current()

    def load_current(self):
        img = self.image_paths[self.current_idx]
        self.canvas.load_image(img)
        ann = img + ".json"
        self.canvas.load_annotations(ann)
        # clear undo stack
        self.undo_stack.clear()
        self.update_title()

    def save_current(self):
        if self.current_idx < 0:
            return
        img = self.image_paths[self.current_idx]
        ann = img + ".json"
        self.canvas.save_annotations(ann)

    def prev_image(self):
        if self.current_idx > 0:
            # self.save_current()
            self.current_idx -= 1
            self.load_current()

    def next_image(self):
        if self.current_idx < len(self.image_paths) - 1:
            # self.save_current()
            self.current_idx += 1
            self.load_current()

    def on_zoom_changed(self, v):
        scale = v / 100.0
        self.canvas.resetTransform()
        self.canvas.scale(scale, scale)

    def on_label_changed(self, idx):
        label = self.combo_labels.currentText()
        for it in self.canvas.scene.selectedItems():
            if isinstance(it, ResizableRotatedBoxItem):
                it.setLabel(label)

    def on_add_class(self):
        text, ok = QInputDialog.getText(self, "Add Class", "Class name:")
        if ok and text.strip():
            new = text.strip()
            if new not in self.classes:
                self.classes.append(new)
                self.combo_labels.addItem(new)
                # also update classes.txt
                with open("classes.txt", "a") as f:
                    f.write(new + "\n")

    def on_box_created(self, box: ResizableRotatedBoxItem):
        self.undo_stack.append(("create", box))

        # Immediately set selected label
        current_label = self.combo_labels.currentText()
        box.setLabel(current_label)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            # delete selected boxes 
            for it in list(self.canvas.scene.selectedItems()):
                if isinstance(it, ResizableRotatedBoxItem):
                    self.undo_stack.append(("delete", it))
                    self.canvas.scene.removeItem(it)
        elif event.key() == Qt.Key_Left:
            self.prev_image()
            event.accept() 
        elif event.key() == Qt.Key_Right:
            self.next_image()
            event.accept() 
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Z:
            # undo
            if not self.undo_stack:
                return
            
            action, obj = self.undo_stack.pop()

            if action == "create":
                if obj.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(obj)
                # self.canvas.scene.removeItem(obj)
            elif action == "delete":
                # self.canvas.scene.addItem(obj)
                if obj.scene() is None: # Only re-add if it's not already there
                    self.canvas.scene.addItem(obj)
                    obj.setSelected(True) # Re-select for convenience 
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_S:
            # Save only when Ctrl+S is pressed
            self.save_current() 
        elif event.key() == Qt.Key_W:
            # Toggle draw mode 
            self.canvas.drawing_mode = not self.canvas.drawing_mode 
            self.update_title() 
            # self.setWindowTitle(f"Image Labeler (Draw Mode: {'ON' if self.canvas.drawing_mode else 'OFF'}): {}")
        else:
            super().keyPressEvent(event)

  
def main():
    import sys
    app = QApplication(sys.argv)
    win = AnnotatorWindow()
    win.resize(800, 800)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

