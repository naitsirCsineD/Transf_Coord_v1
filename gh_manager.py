from github import Github
import os
import base64

def upload_to_github(file_path, remote_path, repo_name, token):
    """
    Sube un archivo local a un repositorio de GitHub.
    """
    try:
        g = Github(token)
        repo = g.get_user().get_repo(repo_name)
        
        with open(file_path, "rb") as f:
            content = f.read()
        
        try:
            # Intentar actualizar si existe
            contents = repo.get_contents(remote_path)
            repo.update_file(contents.path, f"Update {remote_path}", content, contents.sha)
            print(f"Archivo actualizado en GitHub: {remote_path}")
        except:
            # Crear si no existe
            repo.create_file(remote_path, f"Create {remote_path}", content)
            print(f"Archivo creado en GitHub: {remote_path}")
            
        return True
    except Exception as e:
        print(f"Error subiendo a GitHub: {e}")
        return False
