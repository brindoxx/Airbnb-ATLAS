import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Loader2,
  MapPin,
  Compass,
  Sparkles,
  Plane,
  AlertCircle,
  Luggage,
} from "lucide-react";

/**
 * Airbnb Atlas — AI Trip Planner Dashboard
 * ------------------------------------------------
 * Drop this into a Next.js app as app/page.jsx (or pages/index.jsx).
 * Requires: tailwindcss, lucide-react
 *
 * Fonts (add to your root layout <head> or _document):
 * <link rel="preconnect" href="https://fonts.googleapis.com">
 * <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
 */

const API_URL = "http://127.0.0.1:8000/plan_trip";

// ---------- helpers ----------

// Turns the raw itinerary string returned by the backend into
// structured "day" blocks so we can render postcard-style cards.
function parseItinerary(raw) {
  if (!raw) return [];
  const normalized = raw.replace(/\r\n/g, "\n").trim();
  const blocks = normalized.split(/\n\s*\n/).filter(Boolean);

  const dayPattern = /^#{0,3}\s*\*{0,2}\s*(day\s*\d+|morning|afternoon|evening)[:\-\s]*/i;

  const cards = [];
  let current = null;

  blocks.forEach((block) => {
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    const firstLine = lines[0];

    if (dayPattern.test(firstLine) || cards.length === 0) {
      if (current) cards.push(current);
      const titleMatch = firstLine.match(dayPattern);
      const title = titleMatch
        ? firstLine.replace(/^#{0,3}\s*\*{0,2}\s*/, "").replace(/\*{0,2}\s*$/, "")
        : "Trip Overview";
      const bodyLines = titleMatch ? lines.slice(1) : lines;
      current = { title, lines: bodyLines };
    } else {
      current.lines.push(...lines);
    }
  });
  if (current) cards.push(current);

  return cards.map((c) => ({
    title: c.title,
    bullets: c.lines
      .join(" ")
      .split(/(?<=[.!?])\s+(?=[A-Z•\-\*])|(?:^|\n)[\-\*•]\s*/)
      .map((s) => s.replace(/^[\-\*•\s]+/, "").trim())
      .filter((s) => s.length > 3),
  }));
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1 items-center">
      <span className="w-1.5 h-1.5 rounded-full bg-[#B0322B]/50 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#B0322B]/50 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#B0322B]/50 animate-bounce" />
    </span>
  );
}

// ---------- main component ----------

export default function AirbnbAtlas() {
  const [messages, setMessages] = useState([
    {
      role: "ai",
      text:
        "Hi, I'm Atlas. Tell me where you'd like to go (or your current location), and your vibe, budget, and trip duration — I'll pull together a live, personalized itinerary.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [itinerary, setItinerary] = useState(null); // raw string
  const [destinationLabel, setDestinationLabel] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Plain-string transcript mirroring exactly what the backend's
  // AgentState["messages"] expects — this is what gives the Supervisor
  // memory across turns. Kept separate from the UI `messages` state
  // (which stores {role, text} objects for rendering bubbles).
  const historyRef = useRef([]);

  async function handleSend(e) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMessage = { role: "user", text };
    setMessages((prev) => [...prev, userMessage]);
    historyRef.current = [...historyRef.current, text];
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            messages: historyRef.current,
            session_id: sessionId
        }),
      });

      if (!res.ok) throw new Error(`Atlas Engine responded with ${res.status}`);

      const data = await res.json();
      
      if (!sessionId && data.session_id) {
          setSessionId(data.session_id);
      }

      // Record Atlas's reply in the transcript too, so the NEXT request
      // still carries the full back-and-forth for the Supervisor to reason over.
      historyRef.current = [...historyRef.current, data.response];

      if (data.is_clarification) {
        setMessages((prev) => [...prev, { role: "ai", text: data.response }]);
      } else {
        setItinerary(data.response);
        setDestinationLabel(text);
        setMessages((prev) => [
          ...prev,
          { role: "ai", text: "I've generated your itinerary on the right! 🌍" },
        ]);
      }
    } catch (err) {
      setError(
        "Couldn't reach the Atlas Engine at 127.0.0.1:8000. Is the backend running?"
      );
      // Roll back the optimistic push so a failed request doesn't
      // corrupt the transcript sent on the next attempt.
      historyRef.current = historyRef.current.slice(0, -1);
    } finally {
      setLoading(false);
    }
  }

  const cards = itinerary ? parseItinerary(itinerary) : [];

  return (
    <div
      className="h-screen w-full flex bg-gradient-animated text-[#241C1A] overflow-hidden"
      style={{ 
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        backgroundImage: "linear-gradient(135deg, #FFF0E6 0%, #F5F7FA 50%, #FFE6E6 100%)"
      }}
    >
      {/* ================= LEFT: CHAT SIDEBAR (30%) ================= */}
      <aside className="w-full sm:w-[34%] lg:w-[30%] min-w-[320px] h-full flex flex-col border-r border-white/20 bg-white/40 backdrop-blur-xl shadow-[4px_0_24px_rgba(0,0,0,0.03)] z-10">
        {/* Header */}
        <div className="px-6 pt-6 pb-5 border-b border-[#F5EAE2]">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#B0322B] flex items-center justify-center shadow-sm shadow-[#B0322B]/30">
              <Compass className="w-5 h-5 text-white" strokeWidth={2.2} />
            </div>
            <div>
              <h1
                className="text-[19px] leading-tight tracking-tight"
                style={{ fontFamily: "'Fraunces', serif", fontWeight: 600 }}
              >
                Airbnb Atlas
              </h1>
              <p className="text-[11px] text-[#8A7A72] tracking-wide uppercase">
                Live trip concierge
              </p>
            </div>
          </div>
        </div>

        {/* Message thread */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-5 py-5 space-y-4"
        >
          {messages.map((m, i) => (
            <ChatBubble key={i} role={m.role} text={m.text} />
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-[#FBF3EE] border border-[#F0E1D6] px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#B0322B]" />
                <span className="text-[13px] text-[#8A7A72]">
                  Researching, live
                </span>
                <TypingDots />
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-xl bg-[#FDECEA] border border-[#F5C6C0] px-3.5 py-3 text-[12.5px] text-[#8A2E24]">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Input */}
        <form
          onSubmit={handleSend}
          className="px-4 py-4 border-t border-[#F5EAE2] bg-white"
        >
          <div className="flex items-end gap-2 rounded-2xl border border-[#E9DCD2] focus-within:border-[#B0322B] bg-[#FFFBF8] px-3.5 py-2.5 transition-colors">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={1}
              placeholder="Where do you want to go?"
              className="flex-1 resize-none bg-transparent outline-none text-[13.5px] placeholder:text-[#B9A99E] max-h-24 py-1"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send message"
              className="shrink-0 w-9 h-9 rounded-xl bg-[#B0322B] disabled:bg-[#E9DCD2] disabled:cursor-not-allowed flex items-center justify-center transition-colors"
            >
              <Send className="w-4 h-4 text-white" strokeWidth={2.3} />
            </button>
          </div>
        </form>
      </aside>

      {/* ================= RIGHT: ITINERARY MAIN AREA (70%) ================= */}
      <main className="flex-1 h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 sm:px-12 py-12">
          {!itinerary ? (
            <EmptyState />
          ) : (
            <ItineraryView
              destination={destinationLabel}
              cards={cards}
              raw={itinerary}
            />
          )}
        </div>
      </main>
    </div>
  );
}

// ---------- sub components ----------

function ChatBubble({ role, text }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-slide-up-fade`}>
      <div
        className={`max-w-[85%] px-4 py-2.5 text-[13.5px] leading-relaxed shadow-sm ${
          isUser
            ? "bg-[#B0322B] text-white rounded-2xl rounded-br-sm"
            : "bg-white/90 backdrop-blur border border-white/50 text-[#241C1A] rounded-2xl rounded-bl-sm"
        }`}
      >
        {text}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="h-full min-h-[70vh] flex flex-col items-center justify-center text-center gap-4">
      <div className="w-16 h-16 rounded-2xl bg-[#FBF3EE] border border-[#F0E1D6] flex items-center justify-center">
        <Luggage className="w-7 h-7 text-[#B0322B]" strokeWidth={1.8} />
      </div>
      <h2
        className="text-[24px] text-[#241C1A]"
        style={{ fontFamily: "'Fraunces', serif", fontWeight: 600 }}
      >
        Your itinerary will appear here
      </h2>
      <p className="text-[14px] text-[#8A7A72] max-w-sm leading-relaxed">
        Tell Atlas your destination and the vibe you're after in the chat —
        real stays and real places, researched live.
      </p>
    </div>
  );
}

function ItineraryView({ destination, cards, raw }) {
  const searchQuery = destination ? encodeURIComponent(destination) : "travel,landscape";
  const heroImage = `https://loremflickr.com/800/400/${searchQuery}`;

  return (
    <div className="animate-slide-up-fade pb-10">
      {/* Header with Image */}
      <div className="mb-10 relative rounded-3xl overflow-hidden group shadow-xl">
        <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors duration-500 z-10" />
        <img 
          src={heroImage} 
          alt={destination || "Trip Destination"} 
          className="w-full h-64 object-cover transform group-hover:scale-105 transition-transform duration-700"
        />
        <div className="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-black/80 via-black/40 to-transparent z-20">
          <div className="flex items-center gap-1.5 text-white/90 text-[11px] font-semibold tracking-[0.14em] uppercase mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            Generated itinerary
          </div>
          <h1
            className="text-[38px] leading-[1.1] text-white drop-shadow-md"
            style={{ fontFamily: "'Fraunces', serif", fontWeight: 600 }}
          >
            {destination || "Your trip"}
          </h1>
        </div>
      </div>

      {/* Route line + day cards, or plain fallback if parsing found nothing structured */}
      {cards.length > 0 ? (
        <div className="relative pl-8">
          <div className="absolute left-[11px] top-2 bottom-2 w-px bg-gradient-to-b from-[#E9DCD2] via-[#E9DCD2] to-transparent" />
          <div className="space-y-6">
            {cards.map((card, i) => (
              <div key={i} className="relative">
                <div className="absolute -left-8 top-5 w-[22px] h-[22px] rounded-full bg-white border-2 border-[#B0322B] flex items-center justify-center">
                  <MapPin className="w-3 h-3 text-[#B0322B]" strokeWidth={2.5} />
                </div>
                <div className="bg-white/80 backdrop-blur-md rounded-3xl border border-white/40 shadow-[0_4px_20px_-4px_rgba(176,50,43,0.06)] px-6 py-5 hover:shadow-[0_8px_30px_-6px_rgba(176,50,43,0.12)] hover:-translate-y-1 transition-all duration-300">
                  <h3
                    className="text-[17px] mb-2.5 text-[#241C1A]"
                    style={{ fontFamily: "'Fraunces', serif", fontWeight: 600 }}
                  >
                    {card.title}
                  </h3>
                  <ul className="space-y-2">
                    {card.bullets.map((b, j) => (
                      <li
                        key={j}
                        className="text-[13.5px] leading-relaxed text-[#4A3F3A] flex gap-2.5"
                      >
                        <span className="text-[#B0322B] mt-1.5 w-1 h-1 rounded-full bg-[#B0322B] shrink-0" />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-[#F0E1D6] shadow-[0_2px_16px_-4px_rgba(176,50,43,0.08)] px-7 py-6">
          <p className="text-[13.5px] leading-relaxed text-[#4A3F3A] whitespace-pre-line">
            {raw}
          </p>
        </div>
      )}

      <div className="flex items-center gap-2 mt-10 text-[11.5px] text-[#B9A99E]">
        <Plane className="w-3.5 h-3.5" />
        Sourced live for this session — details may change.
      </div>
    </div>
  );
}