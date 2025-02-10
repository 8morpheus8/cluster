import os
import re
import io
import zipfile
import numpy as np
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

# ------------- Функции обработки текста и векторизации -------------

def normalize_line(line):
    """
    Простейшая очистка строки:
      - удаляются лишние пробелы,
      - строка приводится к нижнему регистру.
    В данном варианте мы не заменяем части текста на специальные метки.
    """
    return line.strip().lower()

def get_file_structure(file_content):
    """
    Извлекает текстовую структуру файла:
      - разбивает содержимое на строки,
      - для каждой непустой строки выполняется простая очистка.
    Результат – объединённая строка, представляющая содержимое файла.
    """
    try:
        lines = file_content.split('\n')
        cleaned_lines = [normalize_line(line) for line in lines if line.strip()]
        return ' '.join(cleaned_lines)
    except Exception as e:
        st.error(f"Ошибка обработки файла: {e}")
        return None

def vectorize_structures(structures):
    """
    Векторизует список текстовых представлений с помощью TfidfVectorizer.
    Здесь анализ производится на уровне символов (n-граммы от 3 до 5 символов).
    """
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(3, 5))
    X = vectorizer.fit_transform(structures)
    return X, vectorizer

# ---------------------- Функции визуализации -------------------------

def visualize_clusters(X, labels, file_names, show_colorbar=True):
    """
    Сначала производится уменьшение размерности с помощью PCA (2 компоненты),
    затем строится scatter-плот, где цвет каждой точки соответствует номеру кластера.
    При необходимости можно отобразить цветовую шкалу.
    """
    pca = PCA(n_components=2)
    reduced = pca.fit_transform(X.toarray())
    
    fig, ax = plt.subplots(figsize=(8, 5))
    scatter = ax.scatter(reduced[:, 0], reduced[:, 1], c=labels, cmap='viridis',
                         alpha=0.6, edgecolors='k')
    for i, file_name in enumerate(file_names):
        ax.annotate(file_name, (reduced[i, 0], reduced[i, 1]), fontsize=8, alpha=0.75)
    
    ax.set_title("Кластеры файлов (PCA)")
    if show_colorbar:
        plt.colorbar(scatter, ax=ax)
    return fig

def plot_k_distance(X, min_samples=1):
    """
    Строит график расстояний до k-го ближайшего соседа (где k = min_samples).
    Этот график (метод локтя) помогает оценить оптимальное значение параметра eps.
    """
    X_dense = X.toarray()
    nbrs = NearestNeighbors(n_neighbors=min_samples, metric='cosine').fit(X_dense)
    distances, _ = nbrs.kneighbors(X_dense)
    kth_distances = distances[:, min_samples - 1]
    kth_distances = np.sort(kth_distances)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(kth_distances, marker='o', linestyle='-')
    ax.set_title(f'Метод локтя: расстояния до {min_samples}-го соседа')
    ax.set_xlabel('Точки, отсортированные по расстоянию')
    ax.set_ylabel('Расстояние')
    ax.grid(True)
    st.pyplot(fig)

# --------------------- Обработка загруженных файлов --------------------

def process_files(files):
    """
    Обрабатывает загруженные файлы:
      - для каждого файла пытается прочитать и декодировать содержимое,
      - извлекает текстовую структуру с помощью get_file_structure.
    Возвращает:
      - processed_files: список успешно обработанных файлов,
      - file_names: имена файлов,
      - X: векторизованное представление их структуры.
    """
    processed_files = []
    structures = []
    
    for file in files:
        try:
            content = file.getvalue().decode("utf-8")
        except Exception as e:
            st.error(f"Ошибка декодирования файла {file.name}: {e}")
            continue
        structure = get_file_structure(content)
        if structure:
            processed_files.append(file)
            structures.append(structure)
    
    if not processed_files:
        st.warning("Нет файлов для кластеризации.")
        return None, None, None
    
    X, _ = vectorize_structures(structures)
    file_names = [file.name for file in processed_files]
    return processed_files, file_names, X

# ------------------- Сохранение кластеризованных файлов ------------------

def save_clustered_files(processed_files, labels):
    """
    Сохраняет файлы, распределяя их по папкам в архиве (папки называются cluster_0, cluster_1 и т.д.).
    Возвращает объект BytesIO с архивом в формате ZIP.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file, label in zip(processed_files, labels):
            folder_name = f"cluster_{label}"
            file_path = os.path.join(folder_name, file.name)
            file_content = file.getvalue()  # бинарное содержимое файла
            zip_file.writestr(file_path, file_content)
    zip_buffer.seek(0)
    return zip_buffer

# ------------------------ Основная функция ------------------------------

def main():
    st.title("Кластеризация файлов")
    st.write("Поддерживаемые форматы: .txt, .eml, .sql, .csv")
    
    # Загрузка файлов
    uploaded_files = st.file_uploader("Загрузите файлы",
                                      type=["txt", "eml", "sql", "csv"],
                                      accept_multiple_files=True)
    
    if uploaded_files:
        processed_files, file_names, X = process_files(uploaded_files)
        
        if processed_files is not None:
            st.subheader("Метод локтя для определения параметра eps")
            min_samples_elbow = st.number_input("min_samples для метода локтя", 
                                                min_value=1, value=1, step=1)
            plot_k_distance(X, min_samples=int(min_samples_elbow))
            
            st.subheader("Настройка параметров DBSCAN")
            eps = st.number_input("Введите значение eps (например, 0.05)", 
                                  min_value=0.0, value=0.05, step=0.01, format="%.2f")
            min_samples_dbscan = st.number_input("Введите значение min_samples для DBSCAN", 
                                                 min_value=1, value=1, step=1)
            
            # Кластеризация с использованием DBSCAN и косинусной метрики
            dbscan = DBSCAN(eps=eps, min_samples=int(min_samples_dbscan), metric='cosine')
            labels = dbscan.fit_predict(X)
            
            st.subheader("Результаты кластеризации")
            fig = visualize_clusters(X, labels, file_names)
            st.pyplot(fig)
            
            # Табличное представление распределения файлов по кластерам
            cluster_counts = pd.DataFrame({"Кластер": labels, "Файл": file_names})
            cluster_summary = cluster_counts.groupby("Кластер").count().rename(
                columns={"Файл": "Количество файлов"})
            st.write("### Распределение файлов по кластерам")
            st.dataframe(cluster_summary)
            
            # Сохранение файлов в архив, распределённых по папкам
            if st.button("Сохранить файлы по кластерам"):
                zip_buffer = save_clustered_files(processed_files, labels)
                st.download_button(
                    label="Скачать архив с кластеризованными файлами",
                    data=zip_buffer,
                    file_name="clustered_files.zip",
                    mime="application/zip"
                )

if __name__ == "__main__":
    main()
