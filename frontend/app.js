// frontend/app.js - PARCELS WITH CONNECTING LINES

const API_BASE = "http://localhost:8000";
let ROUTE_ID = null;

const map = L.map("map").setView([52, 20], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap"
}).addTo(map);

let mode = "idle";
let drawMarkers = [];
let drawLine = null;
let routeLayer;
let pickupLayers = [];
let dropLayers = [];
let parcelLines = [];  // NOWE: linie łączące pickup→drop
let parcelPreviewLayers = [];
let startMarker = null;
let endMarker = null;
let isLoading = false;

// Legenda
const legend = L.control({ position: 'bottomright' });
legend.onAdd = function() {
  const div = L.DomUtil.create('div', 'legend');
  div.style.background = 'white';
  div.style.padding = '10px';
  div.style.borderRadius = '5px';
  div.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
  div.style.fontSize = '12px';
  div.innerHTML = `
    <strong>Legenda:</strong><br/>
    <span style="color:blue;">🔵 START trasy</span><br/>
    <span style="color:red;">🔴 END trasy</span><br/>
    <span style="color:green;">🟢 PICKUP (odbiór)</span><br/>
    <span style="color:darkred;">🔴 DROP (dostawa)</span><br/>
    <span style="color:orange;">━━ Paczka (pickup→drop)</span>
  `;
  return div;
};
legend.addTo(map);

function setHint(text, type = "info", duration = 5000) {
  const hint = document.getElementById("hint");
  hint.innerText = text || "";
  hint.className = "";
  if (type === "loading") hint.className = "loading";
  if (type === "success") hint.className = "success";
  if (type === "error") hint.className = "error";
  if (type === "success" && duration > 0) {
    setTimeout(() => {
      if (hint.className === "success") {
        hint.innerText = "";
        hint.className = "";
      }
    }, duration);
  }
}

function showLoading(message = "Ładowanie...") {
  isLoading = true;
  setHint("⏳ " + message, "loading", 0);
}

function hideLoading() {
  isLoading = false;
  const hint = document.getElementById("hint");
  if (hint.className === "loading") {
    hint.innerText = "";
    hint.className = "";
  }
}

function showSuccess(message) {
  setHint("✅ " + message, "success", 5000);
}

function showError(message) {
  setHint("❌ " + message, "error", 0);
}

map.on("click", (e) => {
  if (mode === "idle") return;
  const marker = L.marker(e.latlng, { draggable: true }).addTo(map);
  marker.on("drag", () => updateDrawLine());
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
  parcelLines.forEach(l => map.removeLayer(l));  // NOWE: usuń linie
  pickupLayers = [];
  dropLayers = [];
  parcelLines = [];
}

function clearStartEndMarkers() {
  if (startMarker) { map.removeLayer(startMarker); startMarker = null; }
  if (endMarker) { map.removeLayer(endMarker); endMarker = null; }
}

async function loadMyParcels() {
  const senderId = 9;
  try {
    showLoading("Pobieranie paczek...");
    const r = await fetch(`${API_BASE}/parcels?sender_id=${senderId}`);
    if (!r.ok) throw new Error("Błąd pobierania paczek");
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
    showSuccess(`Załadowano ${data.length} paczek`);
  } catch (error) {
    showError(error.message);
  }
}

async function showParcel(parcelId) {
  try {
    showLoading("Pobieranie paczki...");
    const r = await fetch(`${API_BASE}/parcels/${parcelId}`);
    if (!r.ok) throw new Error("Nie można pobrać paczki");
    const p = await r.json();
    
    parcelPreviewLayers.forEach(l => map.removeLayer(l));
    parcelPreviewLayers = [];
    
    // NOWE: Pobierz współrzędne
    const pickupCoords = p.pickup_point.coordinates;
    const dropCoords = p.drop_point.coordinates;
    
    // Linia łącząca pickup → drop
    const line = L.polyline(
      [[pickupCoords[1], pickupCoords[0]], [dropCoords[1], dropCoords[0]]],
      { color: "orange", weight: 3, dashArray: "5,5" }
    ).addTo(map);
    parcelPreviewLayers.push(line);
    
    const pickup = L.geoJSON(p.pickup_point, {
      pointToLayer: (_, latlng) =>
        L.circleMarker(latlng, { color: "green", radius: 8, fillOpacity: 0.8 })
          .bindPopup(`🟢 PICKUP (odbiór)<br/>Paczka #${parcelId}`)
    }).addTo(map);
    
    const drop = L.geoJSON(p.drop_point, {
      pointToLayer: (_, latlng) =>
        L.circleMarker(latlng, { color: "darkred", radius: 8, fillOpacity: 0.8 })
          .bindPopup(`🔴 DROP (dostawa)<br/>Paczka #${parcelId}`)
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
    const r = await fetch(`${API_BASE}/parcels/${parcelId}`, { method: "DELETE" });
    if (!r.ok) throw new Error("Nie można anulować paczki");
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
  setHint("Tryb TRASY: klikaj kolejne punkty. Minimum 2. Zatwierdź ✅", "info", 0);
}

function startParcelMode() {
  resetDraw();
  mode = "draw_parcel";
  setHint("Tryb PACZKI: 1. klik = PICKUP (odbiór), 2. klik = DROP (dostawa). Zatwierdź ✅", "info", 0);
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
  showSuccess("Anulowano rysowanie");
}

async function createRouteFromPolyline(points) {
  const payloadPoints = points.map(p => ({ lng: p.lng, lat: p.lat }));
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
    showSuccess(`Trasa #${ROUTE_ID} utworzona (${(data.distance_m/1000).toFixed(1)} km)`);
    setTimeout(async () => {
      await loadMatches();
    }, 2000);
  } catch (error) {
    showError(error.message);
    throw error;
  }
}

async function showMyRoutes() {
  try {
    showLoading("Pobieranie tras...");
    const r = await fetch(`${API_BASE}/routes?courier_id=11&active_only=1`);
    if (!r.ok) throw new Error("Błąd pobierania tras");
    const routes = await r.json();
    const container = document.getElementById("matches");
    container.innerHTML = "<h4>Moje trasy</h4>";
    if (routes.length === 0) {
      container.innerHTML += "<em>Brak aktywnych tras. Narysuj nową trasę!</em>";
      hideLoading();
      return;
    }
    for (const route of routes) {
      const matchesRes = await fetch(`${API_BASE}/routes/${route.id}/matches?status=accepted`);
      let parcelsInfo = "";
      if (matchesRes.ok) {
        const matchesData = await matchesRes.json();
        const acceptedParcels = matchesData.items || [];
        if (acceptedParcels.length > 0) {
          const parcelIds = acceptedParcels.map(m => m.parcel_id).join(", ");
          parcelsInfo = `<br/><small>📦 Paczki: ${parcelIds} (${acceptedParcels.length} szt.)</small>`;
        }
      }
      const div = document.createElement("div");
      div.className = "match";
      div.innerHTML = `
        <strong>Trasa #${route.id}</strong><br/>
        Dystans: ${(route.distance_m / 1000).toFixed(1)} km<br/>
        Czas: ${(route.duration_s / 60).toFixed(0)} min${parcelsInfo}<br/>
        <button onclick="selectRoute(${route.id})">👁 Pokaż</button>
        <button onclick="cancelRoute(${route.id})">❌ Anuluj</button>
      `;
      container.appendChild(div);
    }
    showSuccess(`Znaleziono ${routes.length} tras`);
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
    if (!r.ok) throw new Error("Nie można anulować trasy");
    if (ROUTE_ID === routeId) {
      ROUTE_ID = null;
      if (routeLayer) { 
        map.removeLayer(routeLayer); 
        routeLayer = null; 
      }
      clearMatchLayers();
      clearStartEndMarkers();
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
    clearStartEndMarkers();
    
    showLoading("Ładowanie trasy...");
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}`);
    if (!r.ok) throw new Error("Nie można pobrać trasy");
    const data = await r.json();

    routeLayer = L.geoJSON(data.geom, {
      style: { color: "blue", weight: 4 }
    }).addTo(map);

    const startCoords = data.start_point.coordinates;
    const endCoords = data.end_point.coordinates;
    
    startMarker = L.circleMarker([startCoords[1], startCoords[0]], {
      color: "blue",
      fillColor: "blue",
      fillOpacity: 0.8,
      radius: 10
    }).bindPopup("🔵 START trasy").addTo(map);
    
    endMarker = L.circleMarker([endCoords[1], endCoords[0]], {
      color: "red",
      fillColor: "red",
      fillOpacity: 0.8,
      radius: 10
    }).bindPopup("🔴 END trasy").addTo(map);

    map.fitBounds(routeLayer.getBounds());
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

async function loadMatches() {
  if (!ROUTE_ID) {
    document.getElementById("matches").innerHTML = 
      "<em>Wybierz trasę w 'Moje trasy' aby zobaczyć propozycje</em>";
    return;
  }
  try {
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}/matches`);
    if (!r.ok) throw new Error("Błąd pobierania propozycji");
    const data = await r.json();
    const container = document.getElementById("matches");
    container.innerHTML = "";
    clearMatchLayers();
    
    if (!data.items || data.items.length === 0) {
      container.innerHTML = `
        <em style="display:block; text-align:center; padding:20px; background:white; border-radius:4px;">
          Brak propozycji dla tej trasy.<br/>
          Kliknij <strong>🔍 Szukaj propozycji</strong> aby znaleźć paczki w pobliżu.
        </em>
      `;
      return;
    }

    for (const m of data.items) {
      // NOWE: Pobierz współrzędne pickup i drop
      const pickupCoords = m.pickup_point.coordinates;
      const dropCoords = m.drop_point.coordinates;
      
      // NOWE: Linia łącząca pickup → drop
      const line = L.polyline(
        [[pickupCoords[1], pickupCoords[0]], [dropCoords[1], dropCoords[0]]],
        { 
          color: "orange", 
          weight: 2, 
          dashArray: "5,5",
          opacity: 0.7
        }
      ).bindPopup(`Paczka #${m.parcel_id}`).addTo(map);
      parcelLines.push(line);
      
      const pickup = L.geoJSON(m.pickup_point, {
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, { color: "green", radius: 7, fillOpacity: 0.8 })
            .bindPopup(`🟢 PICKUP<br/>Paczka #${m.parcel_id}`)
      }).addTo(map);

      const drop = L.geoJSON(m.drop_point, {
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, { color: "darkred", radius: 7, fillOpacity: 0.8 })
            .bindPopup(`🔴 DROP<br/>Paczka #${m.parcel_id}`)
      }).addTo(map);

      pickupLayers.push(pickup);
      dropLayers.push(drop);

      const div = document.createElement("div");
      div.className = "match";
      div.innerHTML = `
        <strong>Propozycja #${m.id}</strong><br/>
        Paczka #${m.parcel_id}<br/>
        <small>🟢 Odbiór → 🔴 Dostawa</small><br/>
        Δ dystans: +${(m.delta_distance_m / 1000).toFixed(1)} km<br/>
        Δ czas: +${(m.delta_duration_s / 60).toFixed(0)} min<br/>
        <button class="btn-success" onclick="acceptMatch(${m.id})">✅ AKCEPTUJ</button>     
      `;
      container.appendChild(div);
    }
    
    showSuccess(`Znaleziono ${data.items.length} propozycji`);
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
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}/propose`, { method: "POST" });
    if (!r.ok) throw new Error("Błąd przy liczeniu propozycji");
    const data = await r.json();
    await loadMatches();
    if (data.proposals && data.proposals.length > 0) {
      showSuccess(`Znaleziono ${data.proposals.length} nowych propozycji`);
    } else {
      showSuccess("Brak nowych paczek pasujących do trasy");
    }
  } catch (error) {
    showError(error.message);
  }
}

async function acceptMatch(matchId) {
  if (!confirm("Akceptujesz tę paczkę? Zostanie dodana do trasy.")) return;
  try {
    showLoading("Akceptowanie propozycji (przeliczanie trasy)...");
    const r = await fetch(`${API_BASE}/routes/matches/${matchId}/accept`, { method: "POST" });
    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Błąd przy akceptacji");
    }
    const data = await r.json();
    await loadRoute();
    await loadMatches();
    showSuccess(`Zaakceptowano! Nowa trasa: ${(data.new_distance_m/1000).toFixed(1)} km (${data.total_parcels} paczek)`);
  } catch (error) {
    showError(error.message);
  }
}

// INIT
(async function init() {
  try {
    await loadMyParcels();
  } catch (error) {
    console.error("Init error:", error);
  }
})();