import React, { useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import Map from 'react-map-gl/maplibre';
import { HexagonLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { AreaChart, Area, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ShieldAlert, Activity, MapPin } from 'lucide-react';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const INITIAL_VIEW_STATE = {
  longitude: 77.3670,
  latitude: 28.6415,
  zoom: 13.5,
  pitch: 60,
  bearing: 15
};

const DUMMY_POTHOLES = Array.from({ length: 500 }).map(() => ({
  position: [
    77.3670 + (Math.random() - 0.5) * 0.05,
    28.6415 + (Math.random() - 0.5) * 0.05
  ]
}));

const INITIAL_FLEET = [
  { id: 'Phone-1', position: [77.3550, 28.6350] },
  { id: 'Phone-2', position: [77.3750, 28.6450] },
  { id: 'Phone-3', position: [77.3650, 28.6500] },
  { id: 'Phone-4', position: [77.3600, 28.6300] }
];

const DEGRADATION_DATA = [
  { day: 'Mon', score: 95 }, { day: 'Tue', score: 88 },
  { day: 'Wed', score: 75 }, { day: 'Thu', score: 60 },
  { day: 'Fri', score: 45 }, { day: 'Sat', score: 30 },
  { day: 'Sun', score: 15 }
];

export default function App() {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [fleet, setFleet] = useState(INITIAL_FLEET);
  const [anomalies, setAnomalies] = useState([]); // Array to store live YOLO alerts

  // WebSocket Integration for Live Data
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/dashboard');
    
    ws.onopen = () => console.log('Connected to VEEKsha Command Hub');
    
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      
      if (payload.type === 'FLEET_UPDATE') {
        setFleet(payload.data);
      } else if (payload.type === 'CRITICAL_ANOMALY') {
        // Add new anomaly to the map
        setAnomalies(prev => [...prev, payload]);
      }
    };

    return () => ws.close();
  }, []);

  const layers = [
    // 1. Static Road Degradation Layer (3D Towers)
    new HexagonLayer({
      id: 'heatmap',
      data: DUMMY_POTHOLES,
      getPosition: d => d.position,
      radius: 100,
      elevationScale: 50,
      extruded: true,
      coverage: 0.9,
      colorRange: [[30, 41, 59], [234, 179, 8], [239, 68, 68], [220, 38, 38]]
    }),
    
    // 2. Live Moving Phones (Cyan Dots)
    new ScatterplotLayer({
      id: 'live-fleet',
      data: fleet,
      getPosition: d => d.position,
      getFillColor: [6, 182, 212],
      getLineColor: [255, 255, 255],
      lineWidthMinPixels: 2,
      radiusScale: 30,
      getRadius: 1,
      stroked: true,
      transitions: { getPosition: 1000 }
    }),

    // 3. Live Edge AI Alerts (Red Glowing Dots popping up from Python)
    new ScatterplotLayer({
      id: 'live-alerts',
      data: anomalies,
      getPosition: d => d.position,
      getFillColor: [239, 68, 68, 200], // Deep Red
      getLineColor: [255, 0, 0],
      lineWidthMinPixels: 4,
      radiusScale: 60,
      getRadius: 1,
      stroked: true,
      filled: true,
    })
  ];

  return (
    <div className="w-screen h-screen bg-gray-950 overflow-hidden relative font-sans text-slate-100">
      
      <DeckGL layers={layers} initialViewState={viewState} onViewStateChange={({ viewState }) => setViewState(viewState)} controller={true}>
        <Map reuseMaps mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Top Filter Bar */}
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-gray-900/80 backdrop-blur-md border border-cyan-500/30 p-1.5 rounded-full flex gap-2 pointer-events-auto shadow-[0_0_20px_rgba(6,182,212,0.1)] z-10">
        <div className="flex items-center pl-3 pr-1"><MapPin className="w-4 h-4 text-cyan-400" /></div>
        <select className="bg-gray-950 text-xs font-semibold text-slate-200 border border-gray-700 rounded-full px-4 py-1.5 outline-none cursor-pointer"><option>Uttar Pradesh</option></select>
        <select className="bg-gray-950 text-xs font-semibold text-slate-200 border border-gray-700 rounded-full px-4 py-1.5 outline-none cursor-pointer"><option>Ghaziabad</option></select>
        <select className="bg-gray-950 text-xs font-semibold text-cyan-400 border border-cyan-800 rounded-full px-4 py-1.5 outline-none cursor-pointer"><option>Zone: Indirapuram</option></select>
      </div>

      {/* Left Panel */}
      <div className="absolute top-4 left-4 w-96 flex flex-col gap-4 pointer-events-none mt-14">
        <div className="bg-gray-900/70 backdrop-blur-md border border-cyan-500/30 p-4 rounded-lg shadow-[0_0_15px_rgba(6,182,212,0.15)] pointer-events-auto">
          <h1 className="text-2xl font-bold tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-600">
            VEEKSHA <span className="text-sm font-normal text-slate-400 ml-2">OS_v2.0</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider">Urban Intelligence Matrix</p>
        </div>

        <div className="bg-gray-900/70 backdrop-blur-md border border-gray-800 p-4 rounded-lg pointer-events-auto">
          <div className="flex items-center gap-3 mb-3">
            <Activity className="text-cyan-400 w-5 h-5 animate-pulse" />
            <h2 className="text-sm font-semibold uppercase">Active Fleet Stream</h2>
          </div>
          <div className="mt-4 space-y-2">
            {fleet.map((bus) => (
              <div key={bus.id} className="flex justify-between items-center text-[10px] font-mono border-t border-gray-800 pt-2">
                <span className="text-cyan-400">{bus.id}</span>
                <span className="text-slate-500">{bus.position[0].toFixed(4)}, {bus.position[1].toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Panel */}
      <div className="absolute top-4 right-4 w-80 bg-gray-900/70 backdrop-blur-md border border-red-500/20 p-4 rounded-lg pointer-events-auto shadow-[0_0_20px_rgba(239,68,68,0.1)] mt-14">
        <div className="flex items-center gap-2 mb-4">
          <ShieldAlert className="text-red-500 w-5 h-5 animate-pulse" />
          <h2 className="text-sm font-semibold text-red-100 uppercase">Critical Infrastructure</h2>
        </div>
        
        <div className="border-t border-gray-800 pt-4">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Road Health Index (7-Day)</h3>
            <span className="text-[10px] text-red-400 font-mono">-80% Drop</span>
          </div>
          <div className="h-24 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={DEGRADATION_DATA}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <RechartsTooltip contentStyle={{ backgroundColor: '#030712', border: '1px solid #1f2937', fontSize: '10px' }} />
                <Area type="monotone" dataKey="score" stroke="#ef4444" fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

    </div>
  );
}