// frontend/app.js - FIXED VERSION

function setHint(text) {
  document.getElementById("hint").innerText = text || "";
}

const API_BASE = "http://localhost:8000";
let ROUTE_ID = null;

const map = L.map("map").setView([52, 20], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap"
}).addTo(map);

let mode = "idle"; // idle | draw_route | draw_parcel
let drawMarkers = [];
let drawLine = null;

// FIX: Dodane brakujące deklaracje
let routeLayer;
let pickupLayers = [];
let dropLayers = [];
let parcelPreviewLayers = [];

// FIX: Dodany loading state
let isLoading = false;

map.on("click", (e) => {
  if (mode === "idle") return;

  const marker = L.marker(e.latlng, { draggable: true }).addTo(map);

  marker.on("drag", () => {
    updateDrawLine();
  });

  drawMarkers.push(marker);
  updateDrawLine();
});

function updateDrawLine() {
  const latlngs = drawMarkers.map(m => m.getLatLng());

  if (drawLine) {
    drawLine.setLatLngs(latlngs);
  } else {
    drawLine = L.polyline(latlngs, {
      color: mode === "draw_route" ? "blue" : "orange",
      weight: 4,
      dashArray: mode === "draw_parcel" ? "5,5" : null
    }).addTo(map);
  }
}

function clearMatchLayers() {
  pickupLayers.forEach(l => map.removeLayer(l));
  dropLayers.forEach(l => map.removeLayer(l));
  pickupLayers = [];
  dropLayers = [];
}

// FIX: Dodana funkcja pokazująca loading
function showLoading(message = "Ładowanie...") {
  isLoading = true;
  setHint("⏳ " + message);
}

function hideLoading() {
  isLoading = false;
  setHint("");
}

// FIX: Dodana funkcja pokazująca sukces
function showSuccess(message) {
  setHint("✅ " + message);
  setTimeout(() => setHint(""), 3000);
}

// FIX: Dodana funkcja pokazująca błąd
function showError(message) {
  setHint("❌ " + message);
  setTimeout(() => setHint(""), 5000);
}

async function loadMyParcels() {
  const senderId = 9; // MVP

  try {
    showLoading("Pobieranie paczek...");
    const r = await fetch(`${API_BASE}/parcels?sender_id=${senderId}`);
    
    if (!r.ok) {
      throw new Error("Błąd pobierania paczek");
    }

    const data = await r.json();
    const container = document.getElementById("parcels");
    container.innerHTML = "";

    if (data.length === 0) {
      container.innerHTML = "<em>Brak paczek</em>";
      hideLoading();
      return;
    }

    for (const p of data) {
      const div = document.createElement("div");
      div.className = "parcel";
      div.innerHTML = `
        <strong>Paczka #${p.id}</strong><br/>
        Status: <span class="status-${p.status}">${p.status}</span><br/>
        <button onclick="showParcel(${p.id})">👁 Pokaż</button>
        ${p.status !== 'accepted' ? `<button onclick="cancelParcel(${p.id})">❌ Anuluj</button>` : ''}
      `;
      container.appendChild(div);
    }
    
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

async function showParcel(parcelId) {
  try {
    showLoading("Pobieranie paczki...");
    const r = await fetch(`${API_BASE}/parcels/${parcelId}`);
    
    if (!r.ok) {
      throw new Error("Nie można pobrać paczki");
    }

    const p = await r.json();

    parcelPreviewLayers.forEach(l => map.removeLayer(l));
    parcelPreviewLayers = [];

    const pickup = L.geoJSON(p.pickup_point, {
      pointToLayer: (_, latlng) =>
        L.circleMarker(latlng, { color: "green", radius: 7 })
    }).addTo(map);

    const drop = L.geoJSON(p.drop_point, {
      pointToLayer: (_, latlng) =>
        L.circleMarker(latlng, { color: "red", radius: 7 })
    }).addTo(map);

    parcelPreviewLayers.push(pickup, drop);
    map.fitBounds(L.featureGroup(parcelPreviewLayers).getBounds());
    
    showSuccess(`Wyświetlono paczkę #${parcelId}`);
  } catch (error) {
    showError(error.message);
  }
}

async function cancelParcel(parcelId) {
  if (!confirm("Na pewno anulować paczkę?")) return;

  try {
    showLoading("Anulowanie paczki...");
    const r = await fetch(`${API_BASE}/parcels/${parcelId}`, {
      method: "DELETE"
    });

    if (!r.ok) {
      throw new Error("Nie można anulować paczki");
    }

    parcelPreviewLayers.forEach(l => map.removeLayer(l));
    parcelPreviewLayers = [];

    await loadMyParcels();
    showSuccess("Paczka anulowana");
  } catch (error) {
    showError(error.message);
  }
}

function resetDraw() {
  drawMarkers.forEach(m => map.removeLayer(m));
  drawMarkers = [];

  if (drawLine) {
    map.removeLayer(drawLine);
    drawLine = null;
  }

  mode = "idle";
  setHint("");
}

function startRouteMode() {
  resetDraw();
  mode = "draw_route";
  setHint("Tryb TRASY: klikaj kolejne punkty. Minimum 2. Zatwierdź ✅");
}

function startParcelMode() {
  resetDraw();
  mode = "draw_parcel";
  setHint("Tryb PACZKI: kliknij PICKUP (zielony) i DROP (czerwony). Zatwierdź ✅");
}

async function confirmDraw() {
  if (isLoading) return;
  
  if (drawMarkers.length < 2) {
    showError("Potrzebne są co najmniej 2 punkty");
    return;
  }

  const points = drawMarkers.map(m => m.getLatLng());

  try {
    if (mode === "draw_route") {
      await createRouteFromPolyline(points);
    }

    if (mode === "draw_parcel") {
      await createParcelFromPolyline(points[0], points[points.length - 1]);
    }

    resetDraw();
  } catch (error) {
    showError(error.message);
  }
}

function cancelDraw() {
  resetDraw();
}

async function createRouteFromPolyline(points) {
  const payloadPoints = points.map(p => ({
    lng: p.lng,
    lat: p.lat
  }));

  try {
    showLoading("Tworzenie trasy (OSRM routing)...");
    const r = await fetch(`${API_BASE}/routes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        courier_id: 11,
        title: "Trasa z mapy",
        points: payloadPoints
      })
    });

    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Błąd tworzenia trasy");
    }

    const data = await r.json();
    ROUTE_ID = data.id;

    await loadRoute();
    await loadMatches();
    
    showSuccess(`Trasa #${ROUTE_ID} utworzona (${(data.distance_m/1000).toFixed(1)} km)`);
  } catch (error) {
    showError(error.message);
    throw error;
  }
}

async function showMyRoutes() {
  try {
    showLoading("Pobieranie tras...");
    const r = await fetch(`${API_BASE}/routes?courier_id=11&active_only=1`);
    
    if (!r.ok) {
      throw new Error("Błąd pobierania tras");
    }
    
    const routes = await r.json();

    const container = document.getElementById("matches");
    container.innerHTML = "<h4>Moje trasy</h4>";

    if (routes.length === 0) {
      container.innerHTML += "<em>Brak aktywnych tras</em>";
      hideLoading();
      return;
    }

    for (const route of routes) {
      const div = document.createElement("div");
      div.className = "match";
      div.innerHTML = `
        <strong>Trasa #${route.id}</strong><br/>
        Dystans: ${(route.distance_m / 1000).toFixed(1)} km<br/>
        Czas: ${(route.duration_s / 60).toFixed(0)} min<br/>
        <button onclick="selectRoute(${route.id})">👁 Pokaż</button>
        <button onclick="cancelRoute(${route.id})">❌ Anuluj</button>
      `;
      container.appendChild(div);
    }
    
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

async function selectRoute(routeId) {
  ROUTE_ID = routeId;
  await loadRoute();
  await loadMatches();
  showSuccess(`Wyświetlono trasę #${routeId}`);
  mode = "idle";
}

async function cancelRoute(routeId) {
  if (!confirm("Na pewno anulować trasę?")) return;
  
  try {
    showLoading("Anulowanie trasy...");
    const r = await fetch(`${API_BASE}/routes/${routeId}`, { method: "DELETE" });
    
    if (!r.ok) {
      throw new Error("Nie można anulować trasy");
    }
    
    if (ROUTE_ID === routeId) {
      ROUTE_ID = null;
      if (routeLayer) { 
        map.removeLayer(routeLayer); 
        routeLayer = null; 
      }
      clearMatchLayers();
    }
    
    await showMyRoutes();
    showSuccess("Trasa anulowana");
  } catch (error) {
    showError(error.message);
  }
}

async function createParcelFromPolyline(pickup, drop) {
  try {
    showLoading("Dodawanie paczki...");
    const r = await fetch(`${API_BASE}/parcels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sender_id: 9,
        pickup: { lng: pickup.lng, lat: pickup.lat },
        drop: { lng: drop.lng, lat: drop.lat }
      })
    });

    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Nie udało się dodać paczki");
    }

    const data = await r.json();
    await loadMyParcels();
    showSuccess(`Utworzono paczkę #${data.id}`);
  } catch (error) {
    showError(error.message);
    throw error;
  }
}

async function loadRoute() {
  if (!ROUTE_ID) return;
  
  try {
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
    
    showLoading("Ładowanie trasy...");
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}`);
    
    if (!r.ok) {
      throw new Error("Nie można pobrać trasy");
    }
    
    const data = await r.json();

    routeLayer = L.geoJSON(data.geom, {
      style: { color: "blue", weight: 4 }
    }).addTo(map);

    map.fitBounds(routeLayer.getBounds());
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

async function loadMatches() {
  if (!ROUTE_ID) return;

  try {
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}/matches`);
    
    if (!r.ok) {
      throw new Error("Błąd pobierania propozycji");
    }
    
    const data = await r.json();

    const container = document.getElementById("matches");
    container.innerHTML = "";

    clearMatchLayers();
    
    if (!data.items || data.items.length === 0) {
      container.innerHTML = "<em>Brak propozycji dla tej trasy. Kliknij 🔍 Szukaj propozycji.</em>";
      return;
    }

    for (const m of data.items) {
      const pickup = L.geoJSON(m.pickup_point, {
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, { color: "green", radius: 6 })
      }).addTo(map);

      const drop = L.geoJSON(m.drop_point, {
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, { color: "red", radius: 6 })
      }).addTo(map);

      pickupLayers.push(pickup);
      dropLayers.push(drop);

      const div = document.createElement("div");
      div.className = "match";
      div.innerHTML = `
        <strong>Propozycja #${m.id}</strong><br/>
        Paczka #${m.parcel_id}<br/>
        Δ dystans: ${(m.delta_distance_m / 1000).toFixed(1)} km<br/>
        Δ czas: ${(m.delta_duration_s / 60).toFixed(0)} min<br/>
        <small>Pickup → trasa: ${(m.pickup_to_route_m / 1000).toFixed(1)} km</small><br/>
        <small>Drop → trasa: ${(m.drop_to_route_m / 1000).toFixed(1)} km</small><br/>
        <button onclick="acceptMatch(${m.id})">✅ AKCEPTUJ</button>     
      `;
      container.appendChild(div);
    }
  } catch (error) {
    showError(error.message);
  }
}

async function propose() {
  if (!ROUTE_ID) {
    showError("Najpierw wybierz trasę w 'Moje trasy' (👁 Pokaż)");
    return;
  }

  try {
    showLoading("Szukanie propozycji (PostGIS + OSRM)...");
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}/propose`, {
      method: "POST"
    });

    if (!r.ok) {
      throw new Error("Błąd przy liczeniu propozycji");
    }

    const data = await r.json();
    await loadMatches();
    
    if (data.proposals && data.proposals.length > 0) {
      showSuccess(`Znaleziono ${data.proposals.length} propozycji`);
    } else {
      showSuccess("Brak paczek pasujących do trasy");
    }
  } catch (error) {
    showError(error.message);
  }
}

async function acceptMatch(matchId) {
  if (!confirm("Akceptujesz tę paczkę? Trasa zostanie zaktualizowana.")) return;

  try {
    showLoading("Akceptowanie propozycji (przeliczanie trasy)...");
    const r = await fetch(`${API_BASE}/routes/matches/${matchId}/accept`, {
      method: "POST"
    });

    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Błąd przy akceptacji");
    }

    const data = await r.json();
    
    await loadRoute();
    await loadMatches();
    
    showSuccess(`Zaakceptowano! Nowa trasa: ${(data.new_distance_m/1000).toFixed(1)} km`);
  } catch (error) {
    showError(error.message);
  }
}

// INIT
(async function init() {
  try {
    await loadRoute();
    await loadMatches();
    await loadMyParcels();
  } catch (error) {
    console.error("Init error:", error);
  }
})();