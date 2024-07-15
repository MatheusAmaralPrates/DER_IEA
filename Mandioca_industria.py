# Instalar pacotes necessários
!pip install geopandas osmnx networkx folium shapely

import geopandas as gpd
import osmnx as ox
import networkx as nx
import folium
from folium.features import DivIcon
from shapely.geometry import LineString, MultiLineString
from google.colab import drive
from collections import defaultdict
import os

# Montar o Google Drive
drive.mount('/content/drive', force_remount=True)

# Definir os caminhos dos arquivos shapefile
malha_viaria_path = '/content/drive/My Drive/Engenharia/Engenharia_Urbana/malha_viaria_unificada_mandioca/malha_completa.shp'
propriedades_path = '/content/drive/My Drive/Engenharia/Engenharia_Urbana/propriedades_producao_mandioca/Mandioca.shp'
industrias_path = '/content/drive/My Drive/Engenharia/Engenharia_Urbana/industrias_processamento_mandioca/Industrias_Processamento_Mandioca.shp'

# Carregar os arquivos shapefile com colunas necessárias apenas
malha_viaria = gpd.read_file(malha_viaria_path, usecols=['geometry', 'Rodovia'])
propriedades_mandioca = gpd.read_file(propriedades_path, usecols=['geometry'])
industrias_mandioca = gpd.read_file(industrias_path, usecols=['geometry', 'Indústrias'])

# Verificar e garantir que todos os shapefiles estejam no mesmo sistema de coordenadas (EPSG:4326)
for gdf in [malha_viaria, propriedades_mandioca, industrias_mandioca]:
    if not gdf.crs:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs != 'EPSG:4326':
        gdf.to_crs(epsg=4326, inplace=True)

# Verificar se a coluna 'Indústrias' existe, se não, criar uma coluna com valores padrão
if 'Indústrias' not in industrias_mandioca.columns:
    industrias_mandioca['Indústrias'] = [f'Indústria {i+1}' for i in range(len(industrias_mandioca))]

# Mapear nomes específicos das indústrias e seus municípios
industria_names = {
    'Indústria 1': {'Nome': 'FÁBRICA DE FARINHA MANI', 'Município': 'Ocauçu'},
    'Indústria 4': {'Nome': 'CAPROMAL - Cacique Produtos de Mandioca Ltda', 'Município': 'Ribeirão do Sul'},
    'Indústria 5': {'Nome': 'Indústria de Produtos de Mandioca Quero Quero LTDA', 'Município': 'Ocauçu'},
    'Indústria 3': {'Nome': 'LOTUS COMERCIO E INDUSTRIA DE PRODS DE MANDIOCA LTDA', 'Município': 'Cândido Mota'},
}

# Obter os limites da área de interesse a partir das indústrias e propriedades
bounding_box = industrias_mandioca.total_bounds
bbox_propriedades = propriedades_mandioca.total_bounds
bounding_box[0] = min(bounding_box[0], bbox_propriedades[0])
bounding_box[1] = min(bounding_box[1], bbox_propriedades[1])
bounding_box[2] = max(bounding_box[2], bbox_propriedades[2])
bounding_box[3] = max(bounding_box[3], bbox_propriedades[3])

# Criar um grafo de rede de ruas usando OSMnx
G = ox.graph_from_bbox(north=bounding_box[3], south=bounding_box[1], east=bounding_box[2], west=bounding_box[0], network_type='drive')

# Função para encontrar o nó mais próximo no grafo
def nearest_node(G, point):
    return ox.distance.nearest_nodes(G, point.x, point.y)

# Contador para armazenar a frequência de uso de cada segmento de rota
edge_usage = defaultdict(int)
industria_count = defaultdict(int)

# Calcular rotas ótimas de cada propriedade até a indústria mais próxima
rotas = []
for _, propriedade in propriedades_mandioca.iterrows():
    ponto_propriedade = propriedade.geometry
    no_propriedade = nearest_node(G, ponto_propriedade)

    distancia_minima = float('inf')
    rota_otima = None
    industria_destino = None

    for _, industria in industrias_mandioca.iterrows():
        ponto_industria = industria.geometry
        no_industria = nearest_node(G, ponto_industria)

        try:
            rota = nx.shortest_path(G, no_propriedade, no_industria, weight='length')
            distancia = nx.shortest_path_length(G, no_propriedade, no_industria, weight='length')

            if distancia < distancia_minima:
                distancia_minima = distancia
                rota_otima = rota
                industria_destino = industria['Indústrias']
        except nx.NetworkXNoPath:
            continue

    if rota_otima:
        rotas.append(rota_otima)
        industria_count[industria_destino] += 1
        # Incrementar o contador para cada segmento na rota
        for i in range(len(rota_otima) - 1):
            edge_usage[(rota_otima[i], rota_otima[i+1])] += 1

# Função para obter a cor com base na frequência de uso
max_usage = max(edge_usage.values())
def get_color(usage, max_usage):
    if usage > 0.8 * max_usage:
        return 'rgb(255,0,0)'  # Vermelho
    elif usage > 0.6 * max_usage:
        return 'rgb(255,165,0)'  # Laranja
    elif usage > 0.4 * max_usage:
        return 'rgb(255,255,0)'  # Amarelo
    elif usage > 0.2 * max_usage:
        return 'rgb(173,255,47)'  # Verde Amarelado
    else:
        return 'rgb(0,128,0)'  # Verde

# Visualizar as rotas no mapa
m = folium.Map(location=[-22.66, -50.41], zoom_start=12)  # Ajustar para o centro da sua área de interesse

# Adicionar marcadores para propriedades e indústrias
for _, propriedade in propriedades_mandioca.iterrows():
    folium.Marker(location=[propriedade.geometry.y, propriedade.geometry.x], icon=folium.Icon(color='green')).add_to(m)

for _, industria in industrias_mandioca.iterrows():
    nome_industria = industria_names.get(industria['Indústrias'], {}).get('Nome', 'Indústria Desconhecida')
    popup_html = f'<b>{nome_industria}</b><br>Município: {industria_names.get(industria["Indústrias"], {}).get("Município", "Desconhecido")}'
    folium.Marker(location=[industria.geometry.y, industria.geometry.x],
                  icon=folium.Icon(color='red'),
                  popup=folium.Popup(popup_html, max_width=300)).add_to(m)

# Adicionar tabela com contagem de propriedades por indústria
table_html = '<table style="width: 300px; border-collapse: collapse; background: white; border: 1px solid black; font-size: 12px;"><thead><tr><th style="border: 1px solid black; padding: 5px;">Indústria</th><th style="border: 1px solid black; padding: 5px;">Propriedades Mais Próximas</th></tr></thead><tbody>'
for industria, count in industria_count.items():
    nome_industria = industria_names.get(industria, {}).get('Nome', 'Indústria Desconhecida')
    table_html += f'<tr><td style="border: 1px solid black; padding: 5px;">{nome_industria}</td><td style="border: 1px solid black; padding: 5px;">{count}</td></tr>'
table_html += '</tbody></table>'

# Adicionar a tabela ao mapa como um popup
from folium import IFrame
iframe = IFrame(table_html, width=320, height=200)
popup = folium.Popup(iframe, max_width=320)

# Adicionar marcador com popup contendo a tabela
folium.Marker(location=[-22.66, -50.41], icon=folium.Icon(icon='info-sign', color='blue'), popup=popup).add_to(m)

# Adicionar rotas no mapa e label de quantidade
for rota in rotas:
    pontos = [ox.utils_graph.graph_to_gdfs(G, edges=False).loc[no].geometry for no in rota]
    linha = folium.PolyLine(locations=[[p.y, p.x] for p in pontos], color=get_color(edge_usage[(rota[i], rota[i+1])], max_usage), weight=5)
    m.add_child(linha)

# Salvar o mapa como um arquivo HTML localmente
map_file_path = '/content/mapa_mandioca.html'
m.save(map_file_path)

# Exibir mensagem de localização do arquivo salvo
print(f'Mapa salvo localmente em: {map_file_path}')

# Comprimir o arquivo HTML para facilitar o upload no GitHub
import zipfile
with zipfile.ZipFile('/content/mapa_mandioca.zip', 'w') as zipf:
    zipf.write(map_file_path, arcname='mapa_mandioca.html')

# Exibir mensagem de localização do arquivo comprimido
print(f'Mapa comprimido para upload em: /content/mapa_mandioca.zip')

