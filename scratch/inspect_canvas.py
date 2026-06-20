import sys
sys.path.insert(0, 'c:/Users/LUAN/Desktop/Local_Study_RAG_Agent')

from PyQt6.QtWidgets import QApplication
from modules.visualizer.visualizer_controller import VisualizerController

def run_audit():
    app = QApplication(sys.argv)
    controller = VisualizerController()
    canvas = controller._linked_list_tracer._canvas
    
    # 1. Inspect initial properties
    print("--- 1. Initial Canvas Properties ---")
    print(f"Viewport Width: {canvas.viewport().width()}")
    print(f"Viewport Height: {canvas.viewport().height()}")
    print(f"Horizontal ScrollBar Policy: {canvas.horizontalScrollBarPolicy()}")
    print(f"Vertical ScrollBar Policy: {canvas.verticalScrollBarPolicy()}")
    print(f"sceneRect: {canvas.scene().sceneRect()}")
    
    # 2. Simulate sending a frame with 5 nodes
    print("\n--- 2. Simulating Frame (5 nodes) ---")
    payload = {
        "mode": "linked_list",
        "nodes": [
            {"id": "node_0", "val": 10},
            {"id": "node_1", "val": 20},
            {"id": "node_2", "val": 30},
            {"id": "node_3", "val": 40},
            {"id": "node_4", "val": 50},
        ],
        "arrows": [
            ("node_0", "node_1"),
            ("node_1", "node_2"),
            ("node_2", "node_3"),
            ("node_3", "node_4"),
        ],
        "message": "Testing layout spacing"
    }
    
    # Force a specific viewport size for testing
    canvas.resize(600, 300)
    canvas.viewport().resize(600, 300)
    canvas.on_frame_received(payload)
    
    node_count = len(canvas._nodes)
    total_width = canvas._compute_total_width(node_count)
    viewport_width = canvas.viewport().width()
    
    if viewport_width > total_width:
        left_margin = (viewport_width - total_width) / 2
    else:
        left_margin = 60
        
    content_width = left_margin + total_width + 60
    
    print(f"Node Count: {node_count}")
    print(f"Viewport Width (after resize): {viewport_width}")
    print(f"Total Width calculated: {total_width}")
    print(f"Left Margin: {left_margin}")
    print(f"Content Width: {content_width}")
    print(f"sceneRect after frame: {canvas.scene().sceneRect()}")
    
    print("\nPositions:")
    for nid, item in canvas._node_items.items():
        print(f"  {nid}: pos={item.pos()}, x={item.pos().x()}, y={item.pos().y()}")
    print(f"  null_item: pos={canvas._null_item.pos()}, x={canvas._null_item.pos().x()}")
    
    # 3. Simulate resize event
    print("\n--- 3. Simulating Resize to 400x300 ---")
    canvas.resize(400, 300)
    canvas.viewport().resize(400, 300)
    canvas._update_layout_on_resize()
    
    print(f"Viewport Width: {canvas.viewport().width()}")
    print(f"sceneRect after resize: {canvas.scene().sceneRect()}")
    print(f"null_item pos: {canvas._null_item.pos()}")

    controller.close()

if __name__ == "__main__":
    run_audit()
