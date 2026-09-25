import os
import time
import requests
from bs4 import BeautifulSoup

# Hedef Arc'ın Ana Sayfası (Arc 5 İçindekiler Tablosu)
toc_url = "https://witchculttranslation.com/arc-5/"

# Sitenin bizi zararlı bir bot olarak görmemesi için tarayıcı kimliğimiz
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Verilerin kaydedileceği klasörü ayarla
klasor_adi = "veri_havuzu"
if not os.path.exists(klasor_adi):
    os.makedirs(klasor_adi)
    print(f"'{klasor_adi}' klasörü oluşturuldu.")

print("WCT Arc 5 Ana Sayfasına bağlanılıyor...")
response = requests.get(toc_url, headers=headers)

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    content_div = soup.find('div', class_='entry-content')
    
    # Ana sayfadaki tüm geçerli bölüm linklerini topla
    bolum_linkleri = []
    if content_div:
        for a_tag in content_div.find_all('a', href=True):
            href = a_tag['href']
            # Sadece 'chapter' geçen ve başka sitelere gitmeyen linkleri al
            if "chapter" in href.lower() and "arc-5" in href.lower():
                if href not in bolum_linkleri:
                    bolum_linkleri.append(href)
    
    print(f"Toplam {len(bolum_linkleri)} bölüm linki bulundu. İndirme başlıyor...\n")
    
    # Linkleri tek tek gez, içeriği çek ve kaydet
    for index, link in enumerate(bolum_linkleri, start=1):
        print(f"[{index}/{len(bolum_linkleri)}] İndiriliyor: {link}")
        try:
            bolum_response = requests.get(link, headers=headers)
            if bolum_response.status_code == 200:
                bolum_soup = BeautifulSoup(bolum_response.content, 'html.parser')
                
                # Başlığı ve içeriği yakala
                title_element = bolum_soup.find('h1', class_='entry-title')
                title = title_element.text.strip() if title_element else f"Arc 5 Bolum {index}"
                
                b_content_div = bolum_soup.find('div', class_='entry-content')
                if b_content_div:
                    paragraphs = b_content_div.find_all('p')
                    chapter_text = "\n\n".join([p.text.strip() for p in paragraphs if p.text.strip() != ""])
                    
                    # Spoiler etiketlerini göm
                    final_text = f"[Arc 5] [Sezon 3]\nBaşlık: {title}\n\nİçerik:\n{chapter_text}"
                    
                    # Dosyayı veri_havuzu klasörüne yaz
                    dosya_adi = os.path.join(klasor_adi, f"arc5_bolum_{index}.txt")
                    with open(dosya_adi, 'w', encoding='utf-8') as f:
                        f.write(final_text)
            
            # Sunucuyu yormamak ve IP banı yememek için her işlem arası 2 saniye bekle
            time.sleep(2)
            
        except Exception as e:
            print(f"Hata oluştu ({link}): {e}")
            
    print("\nİşlem tamamlandı! Tüm bölümler 'veri_havuzu' klasörüne eklendi.")
else:
    print(f"Ana sayfaya ulaşılamadı. HTTP Kodu: {response.status_code}")