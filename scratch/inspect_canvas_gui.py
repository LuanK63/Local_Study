import sys
sys.path.insert(0, 'c:/Users/LUAN/Desktop/Local_Study_RAG_Agent')
sys.stdout.reconfigure(encoding='utf-8')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from modules.visualizer.visualizer_controller import VisualizerController

def inspect_gui():
    app = QApplication(sys.argv)
    controller = VisualizerController()
    controller.show()
    
    # Select the first linked list algorithm
    # In algo_library.py, what is the ID of singly linked list? Let's check or search.
    # Usually it's "singly_linked_list" or similar.
    # Let's find it by name.
    list_widget = controller._algo_list
    found_item = None
    for i in range(list_widget.count()):
        item = list_widget.item(i)
        if "Insert at Head" in item.text():
            found_item = item
            break
            
    if found_item:
        list_widget.setCurrentItem(found_item)
        controller._on_algo_selected()
        print(f"Selected algorithm: {found_item.text()}")
    else:
        print("Singly Linked List item not found, listing all items:")
        for i in range(list_widget.count()):
            print(f"  {list_widget.item(i).text()}")
            
    # Process events so the window shows up and layouts execute
    app.processEvents()
    
    canvas = controller._linked_list_tracer._canvas
    
    def print_state(label):
        print(f"\n--- State: {label} ---")
        viewport_w = canvas.viewport().width()
        viewport_h = canvas.viewport().height()
        scene_rect = canvas.scene().sceneRect()
        node_count = len(canvas._nodes)
        total_w = canvas._compute_total_width(node_count)
        
        if viewport_w > total_w:
            left_margin = (viewport_w - total_w) / 2
        else:
            left_margin = 60
            
        content_w = left_margin + total_w + 60
        
        print(f"Canvas Viewport Size: {viewport_w} x {viewport_h}")
        print(f"Canvas Size: {canvas.width()} x {canvas.height()}")
        print(f"Node Count: {node_count}")
        print(f"Total Width: {total_w}")
        print(f"Left Margin: {left_margin}")
        print(f"Content Width: {content_w}")
        print(f"sceneRect: {scene_rect}")
        print(f"Horizontal ScrollBar Visible: {canvas.horizontalScrollBar().isVisible()}")
        print(f"Horizontal ScrollBar Range: {canvas.horizontalScrollBar().minimum()} to {canvas.horizontalScrollBar().maximum()}")
        print("Nodes:")
        for nid, item in canvas._node_items.items():
            print(f"  {nid}: pos={item.pos()}, opacity={item.opacity()}, scale={item.scale()}, show_index={item.show_index}")
        print(f"  null_item: pos={canvas._null_item.pos()}, visible={canvas._null_item.isVisible()}")

    # Print state after initial loading
    print_state("Initial Load")
    
    # Now simulate entering a large list to cause horizontal overflow
    controller._array_input.setText("1, 2, 3, 4, 5, 6, 7, 8, 9, 10")
    controller._on_run()
    
    # Let's wait for animations to complete by processing events
    # We can use a timer or a loop with app.processEvents()
    print("\nRunning algorithm...")
    for _ in range(50):
        app.processEvents()
        QApplication.processEvents()
        import time
        time.sleep(0.05)
        
    print_state("After Running (Large list)")
    
    # Resize view to be smaller
    print("\nResizing window to smaller width...")
    controller.resize(500, 600)
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    
    print_state("After Resize")
    
    controller.close()

if __name__ == "__main__":
    inspect_gui()
