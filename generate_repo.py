import os
import re
import hashlib
import zipfile
import shutil
import xml.etree.ElementTree as ET

class KodiRepoGenerator:
    def __init__(self):
        # Skript pracuje v adresáři, kde je spuštěn
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.zips_dir = os.path.join(self.root_dir, "zips")
        self.addons_xml_path = os.path.join(self.zips_dir, "addons.xml")
        self.md5_path = os.path.join(self.zips_dir, "addons.xml.md5")
        self.index_html_path = os.path.join(self.root_dir, "index.html")
        
        # Ignorované složky
        self.ignore = [".git", ".github", ".idea", "zips", "__pycache__", "node_modules"]

    def run(self):
        print("🚀 Spouštím generování Kodi repozitáře...")
        
        # Vytvoření složky zips, pokud neexistuje
        if not os.path.exists(self.zips_dir):
            os.makedirs(self.zips_dir)

        # 1. Najít všechny platné doplňky/skiny kolem skriptu
        addons = self._find_addons()
        if not addons:
            print("❌ Nebyly nalezeny žádné složky obsahující 'addon.xml'!")
            return

        # 2. Vytvořit hlavní spojený addons.xml
        self._create_addons_xml(addons)
        
        # 3. Vytvořit MD5 hash
        self._create_md5()

        # 4. Zabalit doplňky do ZIPů uvnitř složky zips/
        for addon_id, addon_dir, version in addons:
            self._create_zip(addon_id, addon_dir, version)

        # 5. Aktualizovat odkaz a verzi v index.html
        self._update_index_html(addons)

        print("\n✅ Vše hotovo! Složka 'zips' a 'index.html' byly úspěšně aktualizovány.")

    def _find_addons(self):
        addons = []
        for item in os.listdir(self.root_dir):
            item_path = os.path.join(self.root_dir, item)
            if os.path.isdir(item_path) and item not in self.ignore:
                addon_xml_path = os.path.join(item_path, "addon.xml")
                if os.path.exists(addon_xml_path):
                    try:
                        tree = ET.parse(addon_xml_path)
                        root = tree.getroot()
                        addon_id = root.get("id")
                        version = root.get("version")
                        if addon_id and version:
                            addons.append((addon_id, item_path, version))
                            print(f"📦 Nalezen doplněk: {addon_id} (v{version})")
                    except Exception as e:
                        print(f"⚠️ Chyba při čtení {addon_xml_path}: {e}")
        return addons

    def _create_addons_xml(self, addons):
        root = ET.Element("addons")
        for _, addon_dir, _ in addons:
            addon_xml_path = os.path.join(addon_dir, "addon.xml")
            try:
                # Načtení a vložení jednotlivých addon.xml do jednoho velkého souboru
                tree = ET.parse(addon_xml_path)
                root.append(tree.getroot())
            except Exception as e:
                print(f"⚠️ Selhalo vložení XML z {addon_dir}: {e}")
        
        # Uložení spojeného XML do složky zips
        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ", level=0) # Pěkné formátování pro lidi
        tree.write(self.addons_xml_path, encoding="utf-8", xml_declaration=True)
        print(f"📝 Vytvořen soubor: {self.addons_xml_path}")

    def _create_md5(self):
        with open(self.addons_xml_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        with open(self.md5_path, "w", encoding="utf-8") as f:
            f.write(file_hash)
        print(f"🔒 Vytvořen MD5 hash: {self.md5_path}")

    def _create_zip(self, addon_id, addon_dir, version):
        addon_zip_dir = os.path.join(self.zips_dir, addon_id)
        if not os.path.exists(addon_zip_dir):
            os.makedirs(addon_zip_dir)
            
        zip_name = f"{addon_id}-{version}.zip"
        zip_path = os.path.join(addon_zip_dir, zip_name)
        
        # Přepsat starý ZIP novým
        if os.path.exists(zip_path):
            os.remove(zip_path)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(addon_dir):
                for file in files:
                    # Ignorovat git a dočasné soubory uvnitř doplňku
                    if any(x in root or x in file for x in [".git", ".DS_Store", "thumbs.db"]):
                        continue
                    full_path = os.path.join(root, file)
                    # V ZIPu musí být zachována struktura začínající názvem složky doplňku
                    relative_path = os.path.relpath(full_path, os.path.dirname(addon_dir))
                    zipf.write(full_path, relative_path)
                    
        # Zkopírování doprovodných souborů (ikona, fanart, addon.xml) vedle ZIPu pro Kodi
        for meta_file in ["addon.xml", "icon.png", "fanart.jpg"]:
            src = os.path.join(addon_dir, meta_file)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(addon_zip_dir, meta_file))

        print(f"🤐 Zabaleno do ZIPu: {zip_name}")

    def _update_index_html(self, addons):
        if not os.path.exists(self.index_html_path):
            print("⚠️ Soubor index.html nebyl nalezen, přeskakuji jeho aktualizaci.")
            return

        # Najde verzi pro hlavní repozitář 'repository.malyslon'
        repo_version = None
        for addon_id, _, version in addons:
            if addon_id == "repository.malyslon":
                repo_version = version
                break

        if not repo_version:
            print("⚠️ Doplněk 'repository.malyslon' nebyl nalezen, index.html nebyl upraven.")
            return

        with open(self.index_html_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Aktualizuje odkaz href="zips/repository.malyslon/repository.malyslon-X.X.X.zip"
        new_zip_path = f"zips/repository.malyslon/repository.malyslon-{repo_version}.zip"
        content = re.sub(
            r'href="zips/repository\.malyslon/repository\.malyslon-[^"]+\.zip"',
            f'href="{new_zip_path}"',
            content
        )

        # Aktualizuje text verze na tlačítku (vX.X.X .ZIP)
        content = re.sub(
            r'\(v\d+(?:\.\d+)* \.ZIP\)',
            f'(v{repo_version} .ZIP)',
            content
        )

        with open(self.index_html_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"🌐 Aktualizován soubor index.html na verzi v{repo_version}")

if __name__ == "__main__":
    generator = KodiRepoGenerator()
    generator.run()
