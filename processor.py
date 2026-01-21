import zipfile
import pandas as pd
import ezdxf
import xml.etree.ElementTree as ET
from pyproj import Transformer
import os

class KMZProcessor:
    def process_file(self, input_path, output_path):
        """
        Procesa el KMZ y genera el DXF en la ruta de salida.
        """
        # 1. Extraer KML
        kml_content = None
        with zipfile.ZipFile(input_path, 'r') as kmz:
            kml_filename = [f for f in kmz.namelist() if f.endswith('.kml')][0]
            with kmz.open(kml_filename) as kml_file:
                kml_content = kml_file.read()

        # 2. Parsear a DataFrame
        df = self.parse_kml_to_dataframe(kml_content)
        
        # 3. Transformar Coordenadas
        df = self.transform_wgs84_to_psad56(df)
        
        # 4. Limpiar puntos colineales
        df = self.remove_collinear_points(df)
        
        # 5. Generar DXF
        self.create_dxf_from_dataframe(df, output_path)
        return output_path

    def parse_kml_to_dataframe(self, kml_content):
        root = ET.fromstring(kml_content)
        namespace = {"kml": "http://www.opengis.net/kml/2.2"}
        data = []
        placemark_counter = 1

        for folder in root.findall(".//kml:Folder", namespace):
            folder_name = folder.find("kml:name", namespace).text or "Unknown Folder"
            for placemark in folder.findall("kml:Placemark", namespace):
                linestring = placemark.find(".//kml:coordinates", namespace)
                if linestring is not None:
                    coordinates = linestring.text.strip().split()
                    for coord in coordinates:
                        parts = coord.split(",")
                        lon, lat = float(parts[0]), float(parts[1])
                        data.append({
                            "Folder": folder_name,
                            "Placemark_Name": placemark_counter,
                            "Latitude": lat,
                            "Longitude": lon
                        })
                    placemark_counter += 1
        return pd.DataFrame(data)

    def transform_wgs84_to_psad56(self, df):
        # EPSG:24879 es PSAD56 / UTM zone 19S (común en Chile/Perú). Verifica si es tu zona.
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:24879", always_xy=True)
        df['Este_UTM'], df['Norte_UTM'] = zip(*df.apply(
            lambda row: transformer.transform(row['Longitude'], row['Latitude']), axis=1
        ))
        return df

    def are_collinear(self, x1, y1, x2, y2, x3, y3, tolerance=1e-9):
        area = abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0)
        return area < tolerance

    def remove_collinear_points(self, df):
        result = []
        grouped = df.groupby(['Folder', 'Placemark_Name'])
        for _, group in grouped:
            group = group.reset_index(drop=True)
            indices_to_keep = []
            for i in range(len(group)):
                if i == 0 or i == len(group) - 1:
                    indices_to_keep.append(i)
                    continue
                x1, y1 = group.loc[i - 1, ['Este_UTM', 'Norte_UTM']]
                x2, y2 = group.loc[i, ['Este_UTM', 'Norte_UTM']]
                x3, y3 = group.loc[i + 1, ['Este_UTM', 'Norte_UTM']]
                if not self.are_collinear(x1, y1, x2, y2, x3, y3):
                    indices_to_keep.append(i)
            result.append(group.iloc[indices_to_keep])
        return pd.concat(result).reset_index(drop=True) if result else df

    def create_dxf_from_dataframe(self, df, output_file):
        doc = ezdxf.new()
        grouped = df.groupby(['Folder', 'Placemark_Name'])
        for (folder, _), group in grouped:
            # Saneamos el nombre del layer para evitar caracteres inválidos en DXF
            sanitized_layer = "".join(c for c in str(folder) if c.isalnum() or c in " _-")
            if sanitized_layer not in doc.layers:
                doc.layers.add(name=sanitized_layer)
            
            msp = doc.modelspace()
            points = list(zip(group['Este_UTM'], group['Norte_UTM']))
            if points:
                msp.add_lwpolyline(points, dxfattribs={'layer': sanitized_layer})
        doc.saveas(output_file)
