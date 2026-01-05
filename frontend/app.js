// frontend/app.js

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

let routeLayer;
let dropLayers = [];
let parcelPreviewLayers = [];

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

async function loadMyParcels() {
  const senderId = 9; // MVP

  const r = await fetch(`${API_BASE}/parcels?sender_id=${senderId}`);
  if (!r.ok) {
    alert("Błąd pobierania paczek");
    return;
  }

  const data = await r.json();
  const container = document.getElementById("parcels");
  container.innerHTML = "";

  for (const p of data) {
    const div = document.createElement("div");
    div.className = "parcel";
    div.innerHTML = `
      <strong>Paczka #${p.id}</strong><br/>
      Status: ${p.status}<br/>
      <button onclick="showParcel(${p.id})">👁 Pokaż</button>
      <button onclick="cancelParcel(${p.id})">❌ Anuluj</button>
    `;
    container.appendChild(div);
  }
}
async function showParcel(parcelId) {
  const r = await fetch(`${API_BASE}/parcels/${parcelId}`);
  if (!r.ok) {
    alert("Nie można pobrać paczki");
    return;
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
}
async function cancelParcel(parcelId) {
  if (!confirm("Na pewno anulować paczkę?")) return;

  const r = await fetch(`${API_BASE}/parcels/${parcelId}`, {
    method: "DELETE"
  });

  if (!r.ok) {
    alert("Nie można anulować paczki");
    return;
  }

  parcelPreviewLayers.forEach(l => map.removeLayer(l));
  parcelPreviewLayers = [];

  await loadMyParcels();
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
  resetDraw(); // tylko markery szkicu
  mode = "draw_route";
  setHint("Tryb TRASY: klikaj kolejne punkty. Minimum 2. Zatwierdź ✅");
}

function startParcelMode() {
  resetDraw();
  mode = "draw_parcel";
  setHint("Tryb PACZKI: kliknij PICKUP (start) i DROP (koniec). Zatwierdź ✅");
}
async function confirmDraw() {
  if (drawMarkers.length < 2) {
    setHint("Potrzebne są co najmniej 2 punkty");
    return;
  }

  const points = drawMarkers.map(m => m.getLatLng());

  if (mode === "draw_route") {
    await createRouteFromPolyline(points);
  }

  if (mode === "draw_parcel") {
    await createParcelFromPolyline(points[0], points[points.length - 1]);
  }

  resetDraw();
}

function cancelDraw() {
  resetDraw();
}
async function createRouteFromPolyline(points) {
  const payloadPoints = points.map(p => ({
    lng: p.lng,
    lat: p.lat
  }));

  const r = await fetch(`${API_BASE}/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      courier_id: 11,
      title: "Trasa z mapy",
      points: payloadPoints
    })
  });

  const data = await r.json();
  ROUTE_ID = data.id;

  await loadRoute();
  await loadMatches();
}
async function showMyRoutes() {
  const r = await fetch(`${API_BASE}/routes?courier_id=11&active_only=1`);
  const routes = await r.json();

  const container = document.getElementById("matches");
  container.innerHTML = "<h4>Moje trasy</h4>";

  for (const route of routes) {
    const div = document.createElement("div");
    div.className = "match";
    div.innerHTML = `
      <strong>Trasa #${route.id}</strong><br/>
      Dystans: ${(route.distance_m / 1000).toFixed(1)} km<br/>
      <button onclick="selectRoute(${route.id})">Pokaż</button>
      <button onclick="cancelRoute(${route.id})">❌ Anuluj trasę</button>
    `;
    container.appendChild(div);
  }
}
async function selectRoute(routeId) {
  ROUTE_ID = routeId;
  await loadRoute();
  await loadMatches();
  setHint("Wyświetlana trasa kuriera");
  mode = "idle";
}

async function cancelRoute(routeId) {
  if (!confirm("Na pewno anulować trasę?")) return;
  const r = await fetch(`${API_BASE}/routes/${routeId}`, { method: "DELETE" });
  if (!r.ok) {
    alert("Nie można anulować trasy");
    return;
  }
  if (ROUTE_ID === routeId) {
    ROUTE_ID = null;
    if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
    clearMatchLayers();
  }
  await showMyRoutes();
  setHint("Trasa anulowana");
}

async function createParcelFromPolyline(pickup, drop) {
  const r = await fetch(`${API_BASE}/parcels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sender_id: 9,
      pickup: { lng: pickup.lng, lat: pickup.lat },
      drop: { lng: drop.lng, lat: drop.lat }
    })
  });

  const data = await r.json();
  if (!r.ok) {
    alert("Nie udało się dodać paczki");
    return;
  }
  setHint(`Utworzono paczkę ID=${data.id}. Zobacz w 'Moje paczki'.`);
  await loadMyParcels();
}


async function loadRoute() {
  if (!ROUTE_ID) return;
  if (routeLayer) {
    map.removeLayer(routeLayer);
    routeLayer = null;
  }
  const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}`);
  const data = await r.json();

  routeLayer = L.geoJSON(data.geom, {
    style: { color: "blue", weight: 4 }
  }).addTo(map);

  map.fitBounds(routeLayer.getBounds());
}

async function loadMatches() {
  if (!ROUTE_ID) return;

  const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}/matches`);
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
      <strong>Match #${m.id}</strong><br/>
      Δ dystans: ${(m.delta_distance_m / 1000).toFixed(1)} km<br/>
      Δ czas: ${(m.delta_duration_s / 60).toFixed(0)} min<br/>
      <button onclick="acceptMatch(${m.id})">✅ ACCEPT</button>     
    `;
    container.appendChild(div);
  }
}

async function propose() {
  if (!ROUTE_ID) {
    setHint("Najpierw wybierz trasę w 'Moje trasy' (Pokaż), dopiero potem 🔍 Szukaj propozycji")
    return;
  }

  const r = await fetch(`${API_BASE}/routes/${ROUTE_ID}/propose`, {
    method: "POST"
  });

  if (!r.ok) {
    alert("Błąd przy liczeniu propozycji");
    return;
  }

  await loadMatches();
  setHint("Propozycje przeliczone.");  
}

async function acceptMatch(matchId) {
  if (!confirm("Na pewno zaakceptować tę paczkę?")) return;

  const r = await fetch(`${API_BASE}/routes/matches/${matchId}/accept`, {
    method: "POST"
  });

  if (!r.ok) {
    alert("Błąd przy accept");
    return;
  }

  alert("Zaakceptowano. Trasa zaktualizowana.");
  await loadRoute();     // trasa się aktualizuje
  await loadMatches();   // tylko markery paczek
}

// INIT
(async function init() {
  await loadRoute();
  await loadMatches();
})();
