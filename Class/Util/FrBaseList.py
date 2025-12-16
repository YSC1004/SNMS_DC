import sys

# -------------------------------------------------------
# 1. FrCharPtrList (char* 리스트)
#    C++에서는 포인터 메모리 해제가 필요했으나, 
#    Python에서는 문자열 리스트로 관리되며 GC가 자동 처리함.
# -------------------------------------------------------
class FrCharPtrList(list):
    def Clear(self):
        """
        C++: void Clear() - delete elements and clear
        Python: clear()
        """
        self.clear()

# -------------------------------------------------------
# 2. FrStringList (string 리스트)
# -------------------------------------------------------
class FrStringList(list):
    def Copy(self, src):
        """
        C++: void Copy(frStringList& Src)
        기존 내용을 지우고 Src의 내용을 복사
        """
        self.clear()
        self.extend(src) # 리스트 내용 복사

# -------------------------------------------------------
# 3. FrStringVector (string 벡터)
#    Python에서 List와 Vector는 모두 'list'로 통용됨
# -------------------------------------------------------
class FrStringVector(list):
    def Copy(self, src):
        """
        C++: void Copy(frStringVector& Src)
        """
        self.clear()
        self.extend(src)

    def Print(self, start_tag=None, end_tag=None):
        """
        C++: void Print(const char* StartTag, const char* EndTag)
        인덱스와 함께 내용 출력
        """
        if start_tag:
            print(f"[{start_tag}]")

        for i, val in enumerate(self):
            print(f"{i}:[{val}]")

        if end_tag:
            print(f"[{end_tag}]")
        
        # 출력 버퍼 비우기 (C++ frSTD_OUT 특성 반영)
        sys.stdout.flush()

# -------------------------------------------------------
# 4. FrIntVector (int 벡터)
# -------------------------------------------------------
class FrIntVector(list):
    def Copy(self, src):
        """
        C++: void Copy(frIntVector& Src)
        """
        self.clear()
        self.extend(src)

    def Print(self, start_tag=None, end_tag=None):
        """
        C++: void Print(...)
        """
        if start_tag:
            print(f"[{start_tag}]")

        for i, val in enumerate(self):
            print(f"{i}:[{val}]")

        if end_tag:
            print(f"[{end_tag}]")
        
        sys.stdout.flush()