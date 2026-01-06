// frontend/app.js - WITH ROUTE WAYPOINT MARKERS AND DELETE PARCEL

const API_BASE = "http://localhost:8000";
let ROUTE_ID = null;

const map = L.map("map").setView([52, 20], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap"
}).addTo(map);

// NOWE: Paleta kolorów dla segmentów trasy
const SEGMENT_COLORS = [
  '#2196F3', // niebieski
  '#4CAF50', // zielony
  '#FF9800', // pomarańczowy
  '#9C27B0', // fioletowy
  '#F44336', // czerwony
  '#00BCD4', // cyan
  '#FFEB3B', // żółty
  '#795548', // brązowy
  '#607D8B', // szary-niebieski
];

function getSegmentColor(index) {
  return SEGMENT_COLORS[index % SEGMENT_COLORS.length];
}

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
      
      // NOWE: Przycisk usuwania dla paczek cancelled
      let deleteButton = '';
      if (p.status === 'cancelled') {
        deleteButton = `<button class="btn-danger" onclick="deleteParcel(${p.id})" style="margin-top:6px;">🗑 Usuń</button>`;
      }
      
      // NOWE: Przyciski dla delivered
      let deliveryButtons = '';
      if (p.status === 'delivered') {
        deliveryButtons = `
          <button class="btn-success" onclick="confirmDelivery(${p.id})" style="margin-top:6px;">
            ✅ Potwierdź odbiór
          </button>
          <button class="btn-danger" onclick="disputeDelivery(${p.id})" style="margin-top:6px;">
            ❌ Nie otrzymałem
          </button>
        `;
      }
      
      // NOWE: Info dla disputed
      let disputedInfo = '';
      if (p.status === 'disputed') {
        disputedInfo = `
          <small style="color:#ff6600; display:block; margin-top:5px;">
            ⚠️ Zgłoszono problem. Oczekiwanie na odpowiedź kuriera.
          </small>
        `;
      }      
      
      div.innerHTML = `
        <strong>Paczka #${p.id}</strong><br/>
        Status: <span class="status-${p.status}">${p.status}</span><br/>
        ${disputedInfo}        
        <button onclick="showParcel(${p.id})">👁 Pokaż</button>
        ${p.status !== 'accepted' && p.status !== 'cancelled' ? `<button onclick="cancelParcel(${p.id})">❌ Anuluj</button>` : ''}
        ${deleteButton}
        ${deliveryButtons}        
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

// NOWE: Funkcja do fizycznego usuwania paczki
async function deleteParcel(parcelId) {
  if (!confirm("⚠️ UWAGA! Czy na pewno chcesz TRWALE USUNĄĆ tę paczkę z bazy danych?\n\nTej operacji nie można cofnąć!")) return;
  try {
    showLoading("Usuwanie paczki z bazy danych...");
    const r = await fetch(`${API_BASE}/parcels/${parcelId}/permanent`, { method: "DELETE" });
    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Nie można usunąć paczki");
    }
    const data = await r.json();
    parcelPreviewLayers.forEach(l => map.removeLayer(l));
    parcelPreviewLayers = [];
    await loadMyParcels();
    showSuccess(`Paczka #${parcelId} została trwale usunięta`);
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
  // NOWE: Resetuj ROUTE_ID żeby można było dodać nową trasę
  // (ale tylko jeśli nie jesteśmy w trybie przeglądania trasy)
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
    // NOWE: Wyczyść starą trasę z mapy przed dodaniem nowej
    if (routeLayer) {
      routeLayerGroup.clearLayers();
      clearStartEndMarkers();
      clearWaypointMarkers();
      routeLayer = null;
    }
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

// Zamień funkcję showRouteTimeline w app.js

async function showRouteTimeline(routeId) {
  try {
    showLoading("Pobieranie szczegółów trasy...");
    
    // NOWE: Użyj endpointu /segments
    const segmentsRes = await fetch(`${API_BASE}/routes/${routeId}/segments`);
    if (!segmentsRes.ok) throw new Error("Nie można pobrać segmentów trasy");
    const segmentsData = await segmentsRes.json();
    
    const routeRes = await fetch(`${API_BASE}/routes/${routeId}`);
    if (!routeRes.ok) throw new Error("Nie można pobrać trasy");
    const route = await routeRes.json();

    // Pobierz paczki trasy
    const matchesRes = await fetch(`${API_BASE}/routes/${routeId}/matches?status=accepted`);
    const matchesData = await matchesRes.json();
    
    // Pobierz status paczek
    const parcelStatuses = {};
    for (const match of matchesData.items || []) {
      const parcelRes = await fetch(`${API_BASE}/parcels/${match.parcel_id}`);
      if (parcelRes.ok) {
        const parcel = await parcelRes.json();
        parcelStatuses[match.parcel_id] = parcel.status;
      }
    }    

    // Wyczyść waypoints i segmenty
    clearWaypointMarkers();
    routeLayerGroup.clearLayers();
    
    const container = document.getElementById("matches");
    container.innerHTML = `
      <h4>📋 Szczegóły trasy #${routeId}</h4>
      <button onclick="showMyRoutes()">⬅ Wróć do tras</button>
      <button onclick="selectRoute(${routeId})">👁 Pokaż tylko trasę</button>
      <button class="btn-success" onclick="markAllDelivered(${routeId})">✅ Wszystkie dostarczono</button>      
      <hr style="margin:10px 0;"/>
    `;
    
    const timeline = document.createElement("div");
    timeline.style.marginTop = "10px";
    
    const waypoints = segmentsData.waypoints;
    const segments = segmentsData.segments;
    // Podziel waypoints na aktywne i dostarczone
    const activeWaypoints = [];
    const deliveredWaypoints = [];
    
    for (let i = 0; i < waypoints.length; i++) {
      const wp = waypoints[i];
      const status = parcelStatuses[wp.parcel_id];
      
      if (status === 'delivered' || status === 'disputed' || status === 'completed') {
        deliveredWaypoints.push({...wp, index: i, parcelStatus: status});
      } else {
        activeWaypoints.push({...wp, index: i, parcelStatus: status});
      }
    }

    // NARYSUJ TYLKO AKTYWNE SEGMENTY
    for (const wp of activeWaypoints) {
      const i = wp.index;
      if (i >= segments.length) continue;
      
      const segment = segments[i];
      const segmentColor = getSegmentColor(i);
      
      if (segment.geometry && segment.geometry.type === "LineString") {
        const coords = segment.geometry.coordinates.map(c => [c[1], c[0]]); // [lat, lng]
        
        const polyline = L.polyline(coords, {
          color: segmentColor,
          weight: 5,
          opacity: 0.8,
        }).bindPopup(`
          <b>Segment ${i + 1}</b><br/>
          ${waypoints[segment.from_index].label} →<br/>
          ${waypoints[segment.to_index].label}<br/>
          <small>${(segment.distance_m / 1000).toFixed(1)} km, ${(segment.duration_s / 60).toFixed(0)} min</small>
        `).addTo(routeLayerGroup);
      }
    }
    
    // TIMELINE - AKTYWNE PACZKI
    timeline.innerHTML += '<h5 style="margin:15px 0 10px 0;">🚚 W trasie:</h5>';
    
    for (const wp of activeWaypoints) {
      const i = wp.index;
      const wp = waypoints[i];
      const segmentColor = i < segments.length ? getSegmentColor(i) : '#999';
      
      let icon = '📍';
      
      if (wp.type === 'start') {
        icon = '🔵';
      } else if (wp.type === 'end') {
        icon = '🔴';
      } else if (wp.type === 'pickup') {
        icon = '🟢';
      } else if (wp.type === 'drop') {
        icon = '🔴';
      }
      
      // Marker na mapie
      const waypointId = `wp-${wp.type}-${wp.parcel_id || i}`;
      const marker = L.circleMarker([wp.coords[1], wp.coords[0]], {
        color: segmentColor,
        fillColor: segmentColor,
        fillOpacity: 0.8,
        radius: 10,
        weight: 3,
      }).bindPopup(`<b>${i === 0 || i === waypoints.length - 1 ? '' : i + '. '}${wp.label}</b>`).addTo(waypointsLayerGroup);
      
      waypointMarkers[waypointId] = marker;
      
      // Timeline entry
      const displayNumber = (wp.type === 'start' || wp.type === 'end') ? '' : `${i}. `;
      
      let actionButtons = '';
      if (wp.type === 'drop' && wp.parcelStatus === 'accepted') {
        actionButtons = `
          <button class="btn-success" style="margin-top:5px; font-size:11px;" 
                  onclick="markDelivered(${routeId}, ${wp.parcel_id})">
            ✅ Dostarczono
          </button>
        `;
      }      

      timeline.innerHTML += `
        <div style="border-left:4px solid ${segmentColor}; padding-left:10px; margin-bottom:15px; cursor:pointer;"
             onclick="highlightWaypoint('${waypointId}')"
             onmouseover="this.style.background='#f0f0f0'"
             onmouseout="this.style.background='white'">
          <strong>${displayNumber}${icon} ${wp.label}</strong><br/>
          ${wp.type === 'pickup' ? '<small>Odbiór przesyłki</small>' : ''}
          ${wp.type === 'drop' ? '<small>Dostawa przesyłki</small>' : ''}
          ${wp.type === 'start' ? '<small>Początek trasy</small>' : ''}
          ${wp.type === 'end' ? '<small>Koniec trasy</small>' : ''}
          ${actionButtons}
        </div>
      `;
    }
    
    // TIMELINE - DOSTARCZONE PACZKI
    if (deliveredWaypoints.length > 0) {
      timeline.innerHTML += '<hr style="margin:20px 0;"/>';
      timeline.innerHTML += '<h5 style="margin:15px 0 10px 0;">📦 Dostarczone:</h5>';
      
      // Grupuj po paczkach
      const deliveredParcels = {};
      for (const wp of deliveredWaypoints) {
        if (!deliveredParcels[wp.parcel_id]) {
          deliveredParcels[wp.parcel_id] = {
            id: wp.parcel_id,
            status: wp.parcelStatus,
            waypoints: []
          };
        }
        deliveredParcels[wp.parcel_id].waypoints.push(wp);
      }
      
      for (const [parcelId, data] of Object.entries(deliveredParcels)) {
        let statusIcon = '';
        let statusText = '';
        
        if (data.status === 'delivered') {
          statusIcon = '✅';
          statusText = 'Dostarczone (oczekuje na potwierdzenie)';
        } else if (data.status === 'disputed') {
          statusIcon = '⚠️';
          statusText = 'SPÓR - zgłoszony problem';
        } else if (data.status === 'completed') {
          statusIcon = '✔️';
          statusText = 'Potwierdzone';
        }
        
        timeline.innerHTML += `
          <div style="background:#f9f9f9; padding:10px; margin-bottom:10px; border-radius:5px;">
            <strong>${statusIcon} Paczka #${parcelId}</strong><br/>
            <small style="color:#666;">${statusText}</small><br/>
            <button style="margin-top:5px; font-size:11px;" 
                    onclick="showParcelDetails(${parcelId})">
              👁 Pokaż szczegóły
            </button>
          </div>
        `;
      }
    }   

    // Podsumowanie
    const totalSegments = segments.filter(s => !s.error).length;
    timeline.innerHTML += `
      <hr style="margin:10px 0;"/>
      <div style="background:#f0f0f0; padding:10px; border-radius:5px;">
        <strong>Podsumowanie:</strong><br/>
        Całkowity dystans: ${(route.distance_m / 1000).toFixed(1)} km<br/>
        Całkowity czas: ${(route.duration_s / 60).toFixed(0)} min<br/>
        Liczba punktów: ${waypoints.length}<br/>
        Liczba segmentów: ${totalSegments}<br/>
        W trasie: ${activeWaypoints.length}<br/>
        Dostarczone: ${deliveredWaypoints.length}<br/>        
        <small style="color:#666;">💡 Kliknij na punkt aby zobaczyć go na mapie</small><br/>
        <small style="color:#666;">🎨 Każdy segment po drodze ma inny kolor</small>
      </div>
    `;
    
    container.appendChild(timeline);
    
    // Dopasuj mapę TYLKO do aktywnych punktów
    const allPoints = activeWaypoints.map(wp => [wp.coords[1], wp.coords[0]]);
    if (allPoints.length > 0) {
    map.fitBounds(L.latLngBounds(allPoints));
    }    
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

async function markDelivered(routeId, parcelId) {
  if (!confirm("Oznaczasz tę paczkę jako dostarczoną?")) return;
  
  try {
    showLoading("Oznaczanie jako dostarczona...");
    const r = await fetch(
      `${API_BASE}/routes/${routeId}/mark-delivered?parcel_id=${parcelId}`, 
      { method: "POST" }
    );
    
    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Błąd oznaczania");
    }
    
    await showRouteTimeline(routeId);
    showSuccess(`Paczka #${parcelId} oznaczona jako dostarczona`);
  } catch (error) {
    showError(error.message);
  }
}


async function markAllDelivered(routeId) {
  if (!confirm("Oznaczasz WSZYSTKIE paczki jako dostarczone?")) return;
  
  try {
    showLoading("Oznaczanie wszystkich paczek...");
    const r = await fetch(
      `${API_BASE}/routes/${routeId}/mark-all-delivered`, 
      { method: "POST" }
    );
    
    if (!r.ok) throw new Error("Błąd oznaczania");
    
    const data = await r.json();
    await showRouteTimeline(routeId);
    showSuccess(`Oznaczono ${data.delivered_count} paczek jako dostarczone`);
  } catch (error) {
    showError(error.message);
  }
}


async function showParcelDetails(parcelId) {
  // Użyj istniejącej funkcji showParcel
  await showParcel(parcelId);
}

async function confirmDelivery(parcelId) {
  if (!confirm("Potwierdzasz odbiór paczki?")) return;
  
  try {
    showLoading("Potwierdzanie odbioru...");
    const r = await fetch(
      `${API_BASE}/parcels/${parcelId}/confirm-delivery`, 
      { method: "POST" }
    );
    
    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Błąd potwierdzania");
    }
    
    await loadMyParcels();
    showSuccess("Odbiór potwierdzony!");
  } catch (error) {
    showError(error.message);
  }
}


async function disputeDelivery(parcelId) {
  const reason = prompt("Podaj powód problemu z dostawą:");
  if (!reason) return;
  
  try {
    showLoading("Zgłaszanie problemu...");
    const r = await fetch(
      `${API_BASE}/parcels/${parcelId}/dispute-delivery`, 
      { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason })
      }
    );
    
    if (!r.ok) {
      const error = await r.json();
      throw new Error(error.detail || "Błąd zgłaszania");
    }
    
    await loadMyParcels();
    showSuccess("Problem zgłoszony. Kurier został powiadomiony.");
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