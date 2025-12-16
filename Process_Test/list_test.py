import sys
import os

# 라이브러리 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Class.Util.FrBaseList import FrStringList, FrStringVector, FrIntVector

def main():
    print(">> List/Vector Test Start")

    # 1. FrStringList Test
    print("\n[1] FrStringList Copy Test")
    src_list = FrStringList()
    src_list.append("Apple")
    src_list.append("Banana")
    
    dest_list = FrStringList()
    dest_list.append("OldData") # 이는 Copy 시 삭제되어야 함
    
    dest_list.Copy(src_list)
    print(f"   Src: {src_list}")
    print(f"   Dest: {dest_list}") # Apple, Banana가 나와야 함

    # 2. FrStringVector Test
    print("\n[2] FrStringVector Print Test")
    vec = FrStringVector()
    vec.append("Hello")
    vec.append("Python")
    vec.append("World")
    
    vec.Print("START_STR_VEC", "END_STR_VEC")

    # 3. FrIntVector Test
    print("\n[3] FrIntVector Print Test")
    int_vec = FrIntVector()
    int_vec.append(100)
    int_vec.append(200)
    int_vec.append(300)
    
    int_vec.Print("START_INT_VEC", None)

if __name__ == "__main__":
    main()