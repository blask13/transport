// frontend/app.js - WITH ROUTE WAYPOINT MARKERS

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

// Layer groups
let routeLayerGroup = L.layerGroup().addTo(map);
let matchesLayerGroup = L.layerGroup().addTo(map);
let startEndLayerGroup = L.layerGroup().addTo(map);
let waypointsLayerGroup = L.layerGroup().addTo(map); // NOWE: waypoints trasy

let routeLayer;
let pickupLayers = [];
let dropLayers = [];
let parcelLines = [];
let parcelPreviewLayers = [];
let startMarker = null;
let endMarker = null;
let waypointMarkers = {}; // NOWE: mapa markerów waypoints
let isLoading = false;

// Kontrolka warstw
const layerControl = L.control.layers(null, {
  "Trasa": routeLayerGroup,
  "Propozycje paczek": matchesLayerGroup,
  "START/END": startEndLayerGroup,
  "Punkty trasy": waypointsLayerGroup // NOWE
}, { position: 'topright', collapsed: false }).addTo(map);

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
    <span style="color:blue;">🔵 START</span><br/>
    <span style="color:red;">🔴 END</span><br/>
    <span style="color:green;">🟢 PICKUP</span><br/>
    <span style="color:darkred;">🔴 DROP</span><br/>
    <span style="color:#FF6B00;">━━━ Paczka</span>
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
      color: mode === "draw_route" ? "blue" : "#FF6B00",
      weight: mode === "draw_route" ? 4 : 3,
      dashArray: mode === "draw_parcel" ? "8,4" : null
    }).addTo(map);
  }
}

function clearMatchLayers() {
  matchesLayerGroup.clearLayers();
  pickupLayers = [];
  dropLayers = [];
  parcelLines = [];
}

function clearStartEndMarkers() {
  startEndLayerGroup.clearLayers();
  startMarker = null;
  endMarker = null;
}

function clearWaypointMarkers() {
  waypointsLayerGroup.clearLayers();
  waypointMarkers = {};
}

// NOWE: Highlight punktu na mapie
function highlightWaypoint(waypointId) {
  // Reset wszystkich
  Object.values(waypointMarkers).forEach(marker => {
    marker.setStyle({ fillOpacity: 0.6, radius: 8 });
  });
  
  // Highlight wybranego
  if (waypointMarkers[waypointId]) {
    const marker = waypointMarkers[waypointId];
    marker.setStyle({ fillOpacity: 1.0, radius: 12 });
    marker.openPopup();
    map.panTo(marker.getLatLng());
  }
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
    
    const pickupCoords = p.pickup_point.coordinates;
    const dropCoords = p.drop_point.coordinates;
    
    const line = L.polyline(
      [[pickupCoords[1], pickupCoords[0]], [dropCoords[1], dropCoords[0]]],
      { color: "#FF6B00", weight: 3, dashArray: "8,4", opacity: 1.0 }
    ).addTo(map);
    parcelPreviewLayers.push(line);
    
    const pickup = L.geoJSON(p.pickup_point, {
      pointToLayer: (_, latlng) =>
        L.circleMarker(latlng, { color: "green", radius: 8, fillOpacity: 0.8 })
          .bindPopup(`🟢 PICKUP<br/>Paczka #${parcelId}`)
    }).addTo(map);
    
    const drop = L.geoJSON(p.drop_point, {
      pointToLayer: (_, latlng) =>
        L.circleMarker(latlng, { color: "darkred", radius: 8, fillOpacity: 0.8 })
          .bindPopup(`🔴 DROP<br/>Paczka #${parcelId}`)
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
  setHint("Tryb PACZKI: 1. klik = PICKUP, 2. klik = DROP. Zatwierdź ✅", "info", 0);
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
        <button onclick="showRouteTimeline(${route.id})">📋 Szczegóły</button>
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

// NOWE: Timeline z klikalnymi punktami
async function showRouteTimeline(routeId) {
  try {
    showLoading("Pobieranie szczegółów trasy...");
    
    const routeRes = await fetch(`${API_BASE}/routes/${routeId}`);
    if (!routeRes.ok) throw new Error("Nie można pobrać trasy");
    const route = await routeRes.json();
    
    const matchesRes = await fetch(`${API_BASE}/routes/${routeId}/matches?status=accepted`);
    if (!matchesRes.ok) throw new Error("Nie można pobrać paczek");
    const matchesData = await matchesRes.json();
    const acceptedMatches = matchesData.items || [];
    
    // Wyczyść waypoints i dodaj nowe
    clearWaypointMarkers();
    
    const container = document.getElementById("matches");
    container.innerHTML = `
      <h4>📋 Szczegóły trasy #${routeId}</h4>
      <button onclick="showMyRoutes()">⬅ Wróć do tras</button>
      <hr style="margin:10px 0;"/>
    `;
    
    const timeline = document.createElement("div");
    timeline.style.marginTop = "10px";
    
    let waypointIndex = 0;
    
    // START
    const startCoords = route.start_point.coordinates;
    const startWaypointId = `wp-start`;
    const startMarker = L.circleMarker([startCoords[1], startCoords[0]], {
      color: "blue",
      fillColor: "blue",
      fillOpacity: 0.6,
      radius: 8
    }).bindPopup(`<b>START</b><br/>Początek trasy`).addTo(waypointsLayerGroup);
    waypointMarkers[startWaypointId] = startMarker;
    
    timeline.innerHTML += `
      <div style="border-left:3px solid blue; padding-left:10px; margin-bottom:15px; cursor:pointer;"
           onclick="highlightWaypoint('${startWaypointId}')"
           onmouseover="this.style.background='#f0f0f0'"
           onmouseout="this.style.background='white'">
        <strong>🔵 START</strong><br/>
        <small>Początek trasy</small>
      </div>
    `;
    
    // Paczki (pickup i drop)
    for (let i = 0; i < acceptedMatches.length; i++) {
      const match = acceptedMatches[i];
      const pickupCoords = match.pickup_point.coordinates;
      const dropCoords = match.drop_point.coordinates;
      
      waypointIndex++;
      
      // PICKUP marker
      const pickupWaypointId = `wp-pickup-${match.parcel_id}`;
      const pickupMarker = L.circleMarker([pickupCoords[1], pickupCoords[0]], {
        color: "green",
        fillColor: "green",
        fillOpacity: 0.6,
        radius: 8
      }).bindPopup(`<b>${waypointIndex}. PICKUP</b><br/>Paczka #${match.parcel_id}`).addTo(waypointsLayerGroup);
      waypointMarkers[pickupWaypointId] = pickupMarker;
      
      timeline.innerHTML += `
        <div style="border-left:3px solid green; padding-left:10px; margin-bottom:15px; cursor:pointer;"
             onclick="highlightWaypoint('${pickupWaypointId}')"
             onmouseover="this.style.background='#f0f0f0'"
             onmouseout="this.style.background='white'">
          <strong>${waypointIndex}. 🟢 PICKUP - Paczka #${match.parcel_id}</strong><br/>
          <small>Odbiór przesyłki</small><br/>
          ${i > 0 ? `<small style="color:#666;">+${(match.pickup_to_route_m / 1000).toFixed(1)} km</small>` : ''}
        </div>
      `;
      
      waypointIndex++;
      
      // DROP marker
      const dropWaypointId = `wp-drop-${match.parcel_id}`;
      const dropMarker = L.circleMarker([dropCoords[1], dropCoords[0]], {
        color: "darkred",
        fillColor: "darkred",
        fillOpacity: 0.6,
        radius: 8
      }).bindPopup(`<b>${waypointIndex}. DROP</b><br/>Paczka #${match.parcel_id}`).addTo(waypointsLayerGroup);
      waypointMarkers[dropWaypointId] = dropMarker;
      
      timeline.innerHTML += `
        <div style="border-left:3px solid darkred; padding-left:10px; margin-bottom:15px; cursor:pointer;"
             onclick="highlightWaypoint('${dropWaypointId}')"
             onmouseover="this.style.background='#f0f0f0'"
             onmouseout="this.style.background='white'">
          <strong>${waypointIndex}. 🔴 DROP - Paczka #${match.parcel_id}</strong><br/>
          <small>Dostawa przesyłki</small><br/>
          <small style="color:#666;">+${(match.drop_to_route_m / 1000).toFixed(1)} km</small>
        </div>
      `;
    }
    
    // END
    const endCoords = route.end_point.coordinates;
    const endWaypointId = `wp-end`;
    const endMarker = L.circleMarker([endCoords[1], endCoords[0]], {
      color: "red",
      fillColor: "red",
      fillOpacity: 0.6,
      radius: 8
    }).bindPopup(`<b>END</b><br/>Koniec trasy`).addTo(waypointsLayerGroup);
    waypointMarkers[endWaypointId] = endMarker;
    
    timeline.innerHTML += `
      <div style="border-left:3px solid red; padding-left:10px; margin-bottom:15px; cursor:pointer;"
           onclick="highlightWaypoint('${endWaypointId}')"
           onmouseover="this.style.background='#f0f0f0'"
           onmouseout="this.style.background='white'">
        <strong>🔴 END</strong><br/>
        <small>Koniec trasy</small>
      </div>
    `;
    
    // Podsumowanie
    timeline.innerHTML += `
      <hr style="margin:10px 0;"/>
      <div style="background:#f0f0f0; padding:10px; border-radius:5px;">
        <strong>Podsumowanie:</strong><br/>
        Całkowity dystans: ${(route.distance_m / 1000).toFixed(1)} km<br/>
        Całkowity czas: ${(route.duration_s / 60).toFixed(0)} min<br/>
        Liczba paczek: ${acceptedMatches.length}<br/>
        <small style="color:#666;">💡 Kliknij na punkt aby zobaczyć go na mapie</small>
      </div>
    `;
    
    container.appendChild(timeline);
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

async function cancelRoute(routeId) {
  if (!confirm("Na pewno anulować trasę?")) return;
  try {
    showLoading("Anulowanie trasy...");
    const r = await fetch(`${API_BASE}/routes/${routeId}`, { method: "DELETE" });
    if (!r.ok) throw new Error("Nie można anulować trasy");
    if (ROUTE_ID === routeId) {
      ROUTE_ID = null;
      routeLayerGroup.clearLayers();
      clearMatchLayers();
      clearStartEndMarkers();
      clearWaypointMarkers();
      routeLayer = null;
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
    routeLayerGroup.clearLayers();
    clearStartEndMarkers();
    
    showLoading("Ładowanie trasy...");
    const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}`);
    if (!r.ok) throw new Error("Nie można pobrać trasy");
    const data = await r.json();

    routeLayer = L.geoJSON(data.geom, {
      style: { color: "blue", weight: 4 }
    }).addTo(routeLayerGroup);

    const startCoords = data.start_point.coordinates;
    const endCoords = data.end_point.coordinates;
    
    startMarker = L.circleMarker([startCoords[1], startCoords[0]], {
      color: "blue",
      fillColor: "blue",
      fillOpacity: 0.8,
      radius: 10
    }).bindPopup("🔵 START trasy").addTo(startEndLayerGroup);
    
    endMarker = L.circleMarker([endCoords[1], endCoords[0]], {
      color: "red",
      fillColor: "red",
      fillOpacity: 0.8,
      radius: 10
    }).bindPopup("🔴 END trasy").addTo(startEndLayerGroup);

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
      const pickupCoords = m.pickup_point.coordinates;
      const dropCoords = m.drop_point.coordinates;
      
      const line = L.polyline(
        [[pickupCoords[1], pickupCoords[0]], [dropCoords[1], dropCoords[0]]],
        { color: "#FF6B00", weight: 3, dashArray: "8,4", opacity: 1.0 }
      ).bindPopup(`Paczka #${m.parcel_id}`).addTo(matchesLayerGroup);
      parcelLines.push(line);
      
      const pickup = L.geoJSON(m.pickup_point, {
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, { color: "green", radius: 7, fillOpacity: 0.8 })
            .bindPopup(`🟢 PICKUP<br/>Paczka #${m.parcel_id}`)
      }).addTo(matchesLayerGroup);

      const drop = L.geoJSON(m.drop_point, {
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, { color: "darkred", radius: 7, fillOpacity: 0.8 })
            .bindPopup(`🔴 DROP<br/>Paczka #${m.parcel_id}`)
      }).addTo(matchesLayerGroup);

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