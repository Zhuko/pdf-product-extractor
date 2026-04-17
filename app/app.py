import streamlit as st
import pdfplumber
import re
from collections import defaultdict
import pandas as pd
import io

st.set_page_config(
    page_title="PDF Product Extractor",
    page_icon="📄",
    layout="wide"
)

st.title("📄 PDF Product Extractor")
st.markdown("Извлечение данных из разделов **Standard Products** и **Other Products** с группировкой и суммированием")

def parse_product_line(line):
    """Парсит строку с информацией о продукте"""
    patterns = [
        # Паттерн: Название Количество Ед.изм Цена Сумма
        r'(.+?)\s+(\d+(?:\.\d+)?)\s*(шт|кг|м|л|ед|упак|компл)?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',
        # Паттерн: Количество x Название
        r'(\d+(?:\.\d+)?)\s*[xх]\s*(.+?)(?:\s|$)',
        # Паттерн: Название - Количество
        r'(.+?)\s*[-–]\s*(\d+(?:\.\d+)?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, line.strip(), re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                if groups[0].replace('.', '').isdigit():
                    quantity = float(groups[0])
                    name = groups[1].strip()
                else:
                    name = groups[0].strip()
                    quantity = float(groups[1]) if len(groups) > 1 and groups[1] else 1
                
                unit = groups[2] if len(groups) > 2 and groups[2] else "шт"
                price = float(groups[3]) if len(groups) > 3 and groups[3] else 0
                total = float(groups[4]) if len(groups) > 4 and groups[4] else quantity * price
                
                return {
                    'name': name,
                    'quantity': quantity,
                    'unit': unit,
                    'price': price,
                    'total': total
                }
    return None

def extract_products_from_pdf(pdf_file):
    """Извлекает продукты из PDF файла"""
    standard_products = []
    other_products = []
    current_section = None
    in_product_list = False
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            for line in lines:
                if 'standard product' in line.lower():
                    current_section = 'standard'
                    in_product_list = True
                    continue
                elif 'other product' in line.lower():
                    current_section = 'other'
                    in_product_list = True
                    continue
                elif in_product_list and current_section:
                    product_data = parse_product_line(line)
                    if product_data:
                        if current_section == 'standard':
                            standard_products.append(product_data)
                        else:
                            other_products.append(product_data)
    
    return standard_products, other_products

def group_and_sum_products(products):
    """Группирует продукты по названию и суммирует количество"""
    grouped = defaultdict(lambda: {
        'quantity': 0,
        'unit': '',
        'price': 0,
        'total': 0
    })
    
    for product in products:
        name = product['name'].lower().strip()
        grouped[name]['quantity'] += product['quantity']
        grouped[name]['unit'] = product['unit'] or grouped[name]['unit']
        grouped[name]['total'] += product['total']
        if grouped[name]['price'] == 0:
            grouped[name]['price'] = product['price']
        else:
            grouped[name]['price'] = (grouped[name]['price'] + product['price']) / 2
    
    sorted_products = []
    for name in sorted(grouped.keys()):
        data = grouped[name]
        sorted_products.append({
            'Наименование': name.title(),
            'Количество': round(data['quantity'], 2),
            'Ед. изм.': data['unit'] or 'шт',
            'Цена': round(data['price'], 2),
            'Сумма': round(data['total'], 2)
        })
    
    return sorted_products

def to_excel(standard_df, other_df):
    """Конвертирует данные в Excel файл"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not standard_df.empty:
            standard_df.to_excel(writer, sheet_name='Standard Products', index=False)
        if not other_df.empty:
            other_df.to_excel(writer, sheet_name='Other Products', index=False)
        
        all_products = pd.concat([standard_df.assign(Категория='Standard'), 
                                  other_df.assign(Категория='Other')], ignore_index=True)
        all_products.to_excel(writer, sheet_name='All Products', index=False)
    
    output.seek(0)
    return output

# Боковая панель
with st.sidebar:
    st.header("📁 Загрузка файла")
    uploaded_file = st.file_uploader("Выберите PDF файл", type=['pdf'])
    
    if uploaded_file:
        st.success("Файл загружен!")
        
    st.divider()
    st.header("ℹ️ Информация")
    st.markdown("""
    **Приложение извлекает:**
    - Standard products
    - Other products
    
    **Выполняет:**
    - Группировку по названию
    - Суммирование количества
    - Сортировку по алфавиту
    """)

# Основная область
if uploaded_file:
    with st.spinner("🔄 Обработка PDF файла..."):
        try:
            standard_products, other_products = extract_products_from_pdf(uploaded_file)
            standard_grouped = group_and_sum_products(standard_products)
            other_grouped = group_and_sum_products(other_products)
            
            df_standard = pd.DataFrame(standard_grouped) if standard_grouped else pd.DataFrame()
            df_other = pd.DataFrame(other_grouped) if other_grouped else pd.DataFrame()
            
            st.success("✅ Обработка завершена!")
            
            # Вкладки
            tab1, tab2, tab3 = st.tabs(["📦 Standard Products", "📦 Other Products", "📊 Сводка"])
            
            with tab1:
                if not df_standard.empty:
                    st.subheader(f"Standard Products ({len(df_standard)} позиций)")
                    st.dataframe(df_standard, use_container_width=True, hide_index=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Общее количество", f"{df_standard['Количество'].sum():.2f}")
                    with col2:
                        st.metric("Общая сумма", f"{df_standard['Сумма'].sum():.2f}")
                else:
                    st.info("Standard products не найдены в документе")
            
            with tab2:
                if not df_other.empty:
                    st.subheader(f"Other Products ({len(df_other)} позиций)")
                    st.dataframe(df_other, use_container_width=True, hide_index=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Общее количество", f"{df_other['Количество'].sum():.2f}")
                    with col2:
                        st.metric("Общая сумма", f"{df_other['Сумма'].sum():.2f}")
                else:
                    st.info("Other products не найдены в документе")
            
            with tab3:
                st.subheader("Сводная информация")
                
                total_standard_qty = df_standard['Количество'].sum() if not df_standard.empty else 0
                total_standard_sum = df_standard['Сумма'].sum() if not df_standard.empty else 0
                total_other_qty = df_other['Количество'].sum() if not df_other.empty else 0
                total_other_sum = df_other['Сумма'].sum() if not df_other.empty else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего позиций", len(df_standard) + len(df_other))
                with col2:
                    st.metric("Общее количество", f"{total_standard_qty + total_other_qty:.2f}")
                with col3:
                    st.metric("Общая сумма", f"{total_standard_sum + total_other_sum:.2f}")
                
                st.divider()
                
                # Таблица сравнения
                summary_data = {
                    "Категория": ["Standard Products", "Other Products", "ИТОГО"],
                    "Позиций": [len(df_standard), len(df_other), len(df_standard) + len(df_other)],
                    "Количество": [total_standard_qty, total_other_qty, total_standard_qty + total_other_qty],
                    "Сумма": [total_standard_sum, total_other_sum, total_standard_sum + total_other_sum]
                }
                df_summary = pd.DataFrame(summary_data)
                st.dataframe(df_summary, use_container_width=True, hide_index=True)
            
            # Кнопка скачивания Excel
            excel_file = to_excel(df_standard, df_other)
            st.download_button(
                label="📥 Скачать Excel файл",
                data=excel_file,
                file_name="extracted_products.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"❌ Ошибка при обработке: {str(e)}")
            st.info("Попробуйте другой PDF файл или проверьте структуру документа")

else:
    st.info("👈 Загрузите PDF файл в боковой панели для начала работы")
    
    # Демо-пример
    st.divider()
    st.subheader("📋 Пример ожидаемой структуры PDF")
    st.markdown("""
