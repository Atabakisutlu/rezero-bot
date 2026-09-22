import os
import shutil
import re
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# Güncel ve hatasız Google Embedding Sınıfı
class DirectGoogleEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            response = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(response['embedding'])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"
        )
        return response['embedding']

# Veri havuzunu yükle
loader = DirectoryLoader('./veri_havuzu/', glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
splits = text_splitter.split_documents(docs)

persist_directory = "./chroma_db"
if os.path.exists(persist_directory):
    shutil.rmtree(persist_directory)

embeddings = DirectGoogleEmbeddings()
vectorstore = Chroma.from_documents(
    documents=splits, 
    embedding=embeddings, 
    persist_directory=persist_directory
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

def create_spoiler_filter(kullanici_seviyesi):
    def spoiler_filtresi(docs):
        filtrelenmis_docs = []
        seviye_metni = kullanici_seviyesi.lower()
        
        kullanici_arc = 0
        kullanici_sezon = 0
        
        arc_match = re.search(r'arc\s*(\d+)', seviye_metni)
        if arc_match:
            kullanici_arc = int(arc_match.group(1))
            
        sezon_match = re.search(r'sezon\s*(\d+)', seviye_metni)
        if sezon_match:
            kullanici_sezon = int(sezon_match.group(1))
        
        if kullanici_arc == 0 and kullanici_sezon == 0:
            return docs

        for doc in docs:
            metin = doc.page_content
            doc_alt = metin.lower()
            
            doc_arc = 0
            doc_sezon = 0
            
            d_arc_match = re.search(r'arc\s*(\d+)', doc_alt)
            if d_arc_match:
                doc_arc = int(d_arc_match.group(1))
                
            d_sezon_match = re.search(r'sezon\s*(\d+)', doc_alt)
            if d_sezon_match:
                doc_sezon = int(d_sezon_match.group(1))
                
            if kullanici_arc > 0 and doc_arc > 0 and doc_arc > kullanici_arc:
                continue
                
            if kullanici_sezon > 0 and doc_sezon > 0 and doc_sezon > kullanici_sezon:
                continue

            filtrelenmis_docs.append(doc)
            
        return filtrelenmis_docs
    return spoiler_filtresi

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, google_api_key=GOOGLE_API_KEY)

prompt = ChatPromptTemplate.from_template("""
Sen Re:Zero evreninde geçen olayları çok iyi bilen, spoiler koruma protokollerine sıkı sıkıya bağlı, samimi ama profesyonel bir dijital asistansın. Görevin, kullanıcının hikayedeki mevcut ilerleme durumunu ve sana sunulan bağlamı (context) esas alarak soruları yanıtlamaktır.

TEMEL KURALLAR VE KISITLAMALAR:
1. **Kesin Bağlam Sadakati:** Cevaplarını SADECE ve SADECE sana sağlanan bağlamdaki metinlere dayandır. Bağlam dışından asla bilgi getirme.
2. **Asla Spoiler Verme:** Kullanıcının seçtiği sezondan/arc'tan sonraki olaylara, karakter kaderlerine (ölüm, diriliş vb.) veya dönüm noktalarına asla değinme.
3. **Uydurma ve Halüsinasyon Yasaktır:** Eğer sorulan sorunun yanıtı bağlamda net olarak yer almıyorsa, kendi kendine hikaye yazma veya tahmin yürütme.
4. **Standart Hata Mesajı:** Bağlamda bulunmayan veya erişimin kısıtlı olduğu bir bilgi sorulduğunda, yorum yapmadan kelimesi kelimesine şurayı yaz: "Bu bilgi elimdeki kaynaklarda bulunmuyor."
5. **Üslup ve Dil:** Yanıtların her zaman akıcı, gramer açısından kusursuz, doğal bir Türkçe ile olsun; robotik, bozuk veya İngilizce karışık kalıplar kesinlikle kullanma.

Bağlam:
{context}

Soru: {input}
Cevap:
""")

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

class ChatRequest(BaseModel):
    message: str
    level: str

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    filtered_retriever = retriever | create_spoiler_filter(req.level)
    
    rag_chain = (
        {"context": filtered_retriever | format_docs, "input": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    cevap = rag_chain.invoke(req.message)
    return {"reply": cevap}
