import re

def limpiar_texto(texto):
    
    return re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s./-]', '', texto)

def main():
    print("=== Caracteres especiales ===")
    
    while True:
        texto = input("Pon texto o escribe 'Salir' para cerrar el programa :\n\n")
        if texto.lower() == 'salir':
            print("Adiós")
            break
        
        texto_limpio = limpiar_texto(texto)
        
        if texto.strip() == texto_limpio.strip():
            print("\nTexto en orden\nTodo bien\n")
        else:
            print(f"\nSin caracteres:\n\n{texto_limpio}\n")
        
        word_count = len(texto.split())
        char_count = len(texto)
        
        print(f"Palabras    : {word_count}")
        print(f"Caracteres  : {char_count}")

if __name__ == "__main__":
    main()
