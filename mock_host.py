class MockLogger:
    def __init__(self):
        self.logs = []
    
    def info(self, message):
        print(f"[INFO] {message}")
        self.logs.append(("INFO", message))
    
    def error(self, message):
        print(f"[ERROR] {message}")
        self.logs.append(("ERROR", message))
    
    def debug(self, message):
        print(f"[DEBUG] {message}")
        self.logs.append(("DEBUG", message))

class APIHost:
    def __init__(self):
        self.logger = MockLogger()
        self.plugin_mgr = None  # 插件管理器，本地调试时可以为 None 