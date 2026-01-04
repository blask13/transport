\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

🧭 WYTYCZNE STARTOWE PROJEKTU

System dopasowywania tras przejazdów do przesyłek (zamknięta społeczność)

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

1️⃣ CEL PROJEKTU (JASNO I KRÓTKO)

Celem projektu jest stworzenie zamkniętego systemu, który:

•	umożliwia użytkownikom planowanie tras przejazdów po drogach,

•	umożliwia innym użytkownikom zgłaszanie przesyłek (punkt A → punkt B),

•	automatycznie ocenia, czy dana przesyłka może zostać sensownie wpięta w istniejącą trasę,

•	robi to na podstawie rzeczywistego wydłużenia trasy (Δ km / Δ czasu),

•	proponuje przesyłkę kurierowi, bez automatycznego przypisania,

•	po akceptacji aktualizuje trasę i bierze ją pod uwagę w kolejnych dopasowaniach.

System nie jest giełdą, nie jest OLX, nie jest kurierką komercyjną.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

2️⃣ ZAKRES (CO ROBIMY / CZEGO NIE ROBIMY)

✅ ROBIMY

•	routing po drogach (jak nawigacja)

•	zapis tras jako LINESTRING

•	dopasowanie na podstawie kosztu wpięcia

•	ręczna akceptacja przez kuriera

•	zamknięta społeczność (brak anonów)

❌ NIE ROBIMY (na start)

•	płatności

•	licytacji

•	publicznych ogłoszeń

•	optymalizacji wielopaczkowej (VRP)

•	aplikacji mobilnej

Projekt celowo jest MVP, ale technicznie poprawnym.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

3️⃣ ZAŁOŻENIA TECHNICZNE (NIE DO DYSKUSJI)

•	Routing: lokalny silnik (OSRM), offline

•	Geometria: PostGIS (POINT, LINESTRING)

•	Backend: API (FastAPI)

•	Frontend: Web (mapa + formularze)

•	Autoryzacja: konta zatwierdzane ręcznie

•	Środowisko: Docker (jedno środowisko dev = prod-like)

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

4️⃣ GŁÓWNE OBIEKTY SYSTEMU (MENTALNY MODEL)

Myślimy o systemie w tych pojęciach:

•	Użytkownik

o	może być kurierem, nadawcą lub oboma

•	Trasa

o	ma początek, koniec

o	ma geometrię po drogach

o	ma dystans i czas

•	Paczka

o	ma punkt nadania i odbioru

•	Dopasowanie

o	to propozycja, nie decyzja

•	Akceptacja

o	zmienia stan systemu (trasę)

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

5️⃣ KOLEJNOŚĆ PRAC (BARDZO WAŻNE)

ETAP 0 – INFRASTRUKTURA ✅ (ZROBIONE)

•	Docker

•	OSRM

•	API

•	DB

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

ETAP 1 – MODEL DANYCH (TERAZ)

•	projekt tabel PostGIS

•	relacje między trasą a paczką

•	indeksy przestrzenne

👉 Bez tego nie piszemy algorytmu

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

ETAP 2 – ZAPIS DANYCH

•	endpoint dodawania trasy

•	endpoint dodawania paczki

•	walidacja danych

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

ETAP 3 – ALGORYTM DOPASOWANIA

•	zawężanie tras po geometrii

•	liczenie Δ trasy

•	ranking

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

ETAP 4 – FLOW AKCEPTACJI

•	pytanie kuriera

•	timeout

•	aktualizacja trasy

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

ETAP 5 – UX / UI

•	mapa

•	statusy

•	historia

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

6️⃣ ZASADY PROJEKTOWE (ŻEBY SIĘ NIE WYWALIĆ)

•	Najpierw dane, potem logika

•	Jedna trasa = jeden stan prawdy

•	System nigdy nie zmienia trasy bez zgody

•	Brak magii – wszystko policzalne

•	Preferuj prostotę nad „spryt”

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

7️⃣ KRYTERIUM SUKCESU MVP

MVP jest gotowe, jeśli:

•	można dodać trasę,

•	można dodać paczkę,

•	system:

o	znajdzie 3–5 sensownych tras,

o	policzy Δ km / Δ czasu,

•	kurier może:

o	zaakceptować,

o	a trasa się aktualizuje.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

8️⃣ CZEGO PILNOWAĆ OD POCZĄTKU

•	spójnych typów geometrycznych (SRID 4326)

•	nieprzeliczania tras bez potrzeby

•	logowania decyzji (kto, kiedy, dlaczego)

•	tego, że to system pomocniczy, nie decyzyjny

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

9️⃣ JAK TERAZ PRACOWAĆ (PRAKTYCZNIE)

Każdy kolejny krok:

1\.	ma cel

2\.	ma wejście

3\.	ma wyjście

4\.	nie łamie wcześniejszych założeń

Jeśli któryś punkt nie spełnia tych warunków → cofamy się.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

🔚 PODSUMOWANIE

To, co właśnie zrobiłeś (OSRM + API), to najtrudniejsza technicznie część.

Od teraz projekt jest czysto inżynierski, nie „kombinowany”.





