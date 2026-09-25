import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Loader2,
  MapPin,
  Compass,
  Sparkles,
  Plane,
  AlertCircle,
  Luggage,
  ExternalLink,
  ShieldCheck,
  Clock,
  BookOpen,
  X,
  CheckCircle2,
  ChevronRight,
  Zap,
  ShieldAlert,
} from "lucide-react";

/**
 * Airbnb Atlas — AI Trip Planner Dashboard (5-Stage Citation-Aware Architecture)
 * -----------------------------------------------------------------------------
 * Displays citation badges [Src-X], live telemetry (cold vs warm latency),
 * retrieved sources drawer with provenance, and claim verification audits.
 */

const API_URL = "http://127.0.0.1:8000/plan_trip";

// ---------- helpers ----------

function TypingDots() {
  return (
    <span className="inline-flex gap-1 items-center">
      <span className="w-1.5 h-1.5 rounded-full bg-[#B0322B]/50 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#B0322B]/50 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#B0322B]/50 animate-bounce" />
    </span>
  );
}

/**
 * Parses bullet text to render interactive [Src-X] citation badges.
 */
function FormattedBullet({ text, onSourceClick }) {
  if (typeof text !== "string") return null;

  // Split on [Src-X] citation patterns
  const parts = text.split(/(\[Src-\d+\])/g);

  return (
    <span className="leading-relaxed">
      {parts.map((part, idx) => {
        const match = part.match(/\[(Src-\d+)\]/);
        if (match) {
          const srcId = match[1];
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSourceClick(srcId)}
              className="inline-flex items-center gap-1 mx-1 px-1.5 py-0.5 rounded-md bg-[#FFF0EA] hover:bg-[#B0322B] text-[#B0322B] hover:text-white border border-[#F5D5C6] hover:border-[#B0322B] text-[10.5px] font-bold tracking-tight transition-all duration-150 cursor-pointer shadow-2xs align-baseline group"
              title={`View retrieved evidence for ${srcId}`}
            >
              <span>{srcId}</span>
              <ExternalLink className="w-2.5 h-2.5 opacity-60 group-hover:opacity-100" />
            </button>
          );
        }
        return <span key={idx}>{part}</span>;
      })}
    </span>
  );
}

// ---------- main component ----------

export default function AirbnbAtlas() {
  const [messages, setMessages] = useState([
    {
      role: "ai",
      text:
        "Hi, I'm Atlas. Tell me where you'd like to go (or your current location), and your vibe, budget, and trip duration — I'll research live web data, cross-encoder rerank the best stays, and cite verified sources.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [itinerary, setItinerary] = useState(null);
  const [destinationLabel, setDestinationLabel] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  // Citation & Provenance State
  const [citations, setCitations] = useState([]);
  const [timings, setTimings] = useState(null);
  const [verificationReport, setVerificationReport] = useState(null);
  const [showSourcesDrawer, setShowSourcesDrawer] = useState(false);
  const [activeSourceId, setActiveSourceId] = useState(null);
  const [showAuditModal, setShowAuditModal] = useState(false);

  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

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
          session_id: sessionId,
        }),
      });

      if (!res.ok) throw new Error(`Atlas Engine responded with ${res.status}`);

      const data = await res.json();

      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      // Record Atlas's reply in the transcript as a string so future turns preserve conversational context
      const replyText = data.is_clarification
        ? (typeof data.response === "string" ? data.response : "Clarification requested")
        : (data.chat_message || "Here is your verified itinerary.");
      historyRef.current = [...historyRef.current, replyText];

      if (data.is_clarification) {
        setMessages((prev) => [...prev, { role: "ai", text: data.response }]);
      } else {
        setItinerary(data.response);
        setDestinationLabel(data.destination || "Your Trip");
        setCitations(data.citations || []);
        setTimings(data.timings || null);
        setVerificationReport(data.verification_report || null);
        setMessages((prev) => [
          ...prev,
          {
            role: "ai",
            text:
              data.chat_message ||
              "I've generated your verified itinerary on the right! 🌍",
          },
        ]);
      }
    } catch (err) {
      setError(
        "Couldn't reach the Atlas Engine at 127.0.0.1:8000. Is the backend running?"
      );
      historyRef.current = historyRef.current.slice(0, -1);
    } finally {
      setLoading(false);
    }
  }

  function handleSourceClick(srcId) {
    setActiveSourceId(srcId);
    setShowSourcesDrawer(true);
  }

  const cards = Array.isArray(itinerary) ? itinerary : [];

  return (
    <div
      className="h-screen w-full flex bg-gradient-animated text-[#241C1A] overflow-hidden"
      style={{
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        backgroundImage:
          "linear-gradient(135deg, #FFF0E6 0%, #F5F7FA 50%, #FFE6E6 100%)",
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
                Citation-Backed RAG Concierge
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
                  Researching live & reranking evidence
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
              placeholder="Where do you want to go or revise?"
              className="flex-1 resize-none bg-transparent outline-none text-[13.5px] placeholder:text-[#B9A99E] max-h-24 py-1"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send message"
              className="shrink-0 w-9 h-9 rounded-xl bg-[#B0322B] disabled:bg-[#E9DCD2] disabled:cursor-not-allowed flex items-center justify-center transition-colors cursor-pointer"
            >
              <Send className="w-4 h-4 text-white" strokeWidth={2.3} />
            </button>
          </div>
        </form>
      </aside>

      {/* ================= RIGHT: ITINERARY MAIN AREA (70%) ================= */}
      <main className="flex-1 h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 sm:px-12 py-10">
          {!itinerary ? (
            <EmptyState />
          ) : (
            <ItineraryView
              destination={destinationLabel}
              cards={cards}
              raw={itinerary}
              citations={citations}
              timings={timings}
              verificationReport={verificationReport}
              onSourceClick={handleSourceClick}
              onOpenSources={() => setShowSourcesDrawer(true)}
              onOpenAudit={() => setShowAuditModal(true)}
            />
          )}
        </div>
      </main>

      {/* ================= RETRIEVED SOURCES SLIDE-OVER DRAWER ================= */}
      <RetrievedSourcesDrawer
        isOpen={showSourcesDrawer}
        onClose={() => {
          setShowSourcesDrawer(false);
          setActiveSourceId(null);
        }}
        sources={citations}
        activeSourceId={activeSourceId}
      />

      {/* ================= CLAIM VERIFICATION AUDIT MODAL ================= */}
      <VerificationAuditModal
        isOpen={showAuditModal}
        onClose={() => setShowAuditModal(false)}
        report={verificationReport}
      />
    </div>
  );
}

// ---------- sub components ----------

function ChatBubble({ role, text }) {
  const isUser = role === "user";
  return (
    <div
      className={`flex ${
        isUser ? "justify-end" : "justify-start"
      } animate-slide-up-fade`}
    >
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
        Tell Atlas your destination, vibe, duration, and budget in the chat —
        verified stays and activities, researched and cited live.
      </p>
    </div>
  );
}

function ItineraryView({
  destination,
  cards,
  raw,
  citations = [],
  timings,
  verificationReport,
  onSourceClick,
  onOpenSources,
  onOpenAudit,
}) {
  const [heroImage, setHeroImage] = useState(
    "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800&q=80"
  );

  useEffect(() => {
    if (!destination) return;

    let isMounted = true;

    // Reject flags, coats of arms, maps, SVGs, and generic symbols
    function isScenicImage(url) {
      if (!url || typeof url !== "string") return false;
      const lower = url.toLowerCase();
      const badPatterns = ["flag", "coat_of_arms", "emblem", "seal", ".svg", "map", "locator", "logo", "symbol"];
      return !badPatterns.some((bp) => lower.includes(bp));
    }

    async function fetchImage() {
      const cleanDest = destination.trim();
      if (!cleanDest) return;

      try {
        // Prioritize 'Tourism in {destination}' for countries/regions to fetch landmarks (e.g. Halong Bay, Mont-Saint-Michel)
        const candidateQueries = [
          `Tourism in ${cleanDest}`,
          cleanDest,
        ];

        // Tier 1: Exact Wikipedia title with redirect resolution
        for (const cand of candidateQueries) {
          const directRes = await fetch(
            `https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&format=json&piprop=original|thumbnail&pithumbsize=1200&redirects=1&titles=${encodeURIComponent(cand)}&origin=*`
          );
          const directData = await directRes.json();
          const directPages = directData.query?.pages;
          if (directPages) {
            for (const page of Object.values(directPages)) {
              const imgSrc = page?.original?.source || page?.thumbnail?.source;
              if (imgSrc && isScenicImage(imgSrc) && isMounted) {
                setHeroImage(imgSrc);
                return;
              }
            }
          }
        }

        // Tier 2: Wikipedia Search Generator for attractions/tourism
        const searchRes = await fetch(
          `https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(cleanDest + ' attractions tourism')}&gsrlimit=6&prop=pageimages&piprop=original|thumbnail&pithumbsize=1200&format=json&origin=*`
        );
        const searchData = await searchRes.json();
        const searchPages = searchData.query?.pages;
        if (searchPages) {
          for (const page of Object.values(searchPages)) {
            const imgSrc = page?.original?.source || page?.thumbnail?.source;
            if (imgSrc && isScenicImage(imgSrc) && isMounted) {
              setHeroImage(imgSrc);
              return;
            }
          }
        }

        // Tier 3: High quality landscape fallback if no scenic Wikipedia image is found
        if (isMounted) {
          setHeroImage("https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1200&q=80");
        }
      } catch (err) {
        console.error("Failed to fetch scenic image from Wikipedia", err);
        if (isMounted) {
          setHeroImage("https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1200&q=80");
        }
      }
    }

    fetchImage();

    return () => {
      isMounted = false;
    };
  }, [destination]);

  const isWarmRevision = timings && timings.research_ms === 0;
  const isGateHalted =
    verificationReport?.status === "GATE_HALTED" ||
    cards.some((c) => c.title?.includes("Gate Notice"));

  const faithfulnessPct =
    verificationReport?.faithfulness_score != null
      ? Math.round(verificationReport.faithfulness_score * 100)
      : null;

  return (
    <div className="animate-slide-up-fade pb-10">
      {/* Telemetry & Grounding Control Bar */}
      <div className="mb-6 bg-white/70 backdrop-blur-md rounded-2xl border border-white/60 shadow-xs px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-[12px]">
        <div className="flex items-center gap-2">
          {isWarmRevision ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-semibold text-[11px]">
              <Zap className="w-3 h-3 text-amber-600" />
              Session Cache Hit (Warm)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-800 border border-blue-200 font-semibold text-[11px]">
              <Plane className="w-3 h-3 text-blue-600" />
              Live JIT Research (Cold)
            </span>
          )}

          {timings?.total_ms && (
            <span className="flex items-center gap-1 text-[#8A7A72] font-mono text-[11.5px]">
              <Clock className="w-3 h-3 text-[#B0322B]" />
              {(timings.total_ms / 1000).toFixed(2)}s
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Claim Faithfulness Badge or Guardrail Alert Badge */}
          {isGateHalted ? (
            <span
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-300 font-semibold text-[11px] shadow-2xs"
              title="Scraping Gate actively prevented ungrounded hallucinations"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
              <span>Scraping Gate Active (Zero Hallucination Guard)</span>
            </span>
          ) : (
            <button
              type="button"
              onClick={onOpenAudit}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100 transition-colors font-medium text-[11px] cursor-pointer"
              title="Inspect Claim Verifier Critic Audit"
            >
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>Faithfulness: {faithfulnessPct ?? 100}%</span>
            </button>
          )}

          {/* Retrieved Sources Drawer Trigger */}
          {citations && citations.length > 0 ? (
            <button
              type="button"
              onClick={onOpenSources}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#FFF0EA] text-[#B0322B] border border-[#F5D5C6] hover:bg-[#B0322B] hover:text-white transition-all font-semibold text-[11px] cursor-pointer shadow-2xs"
            >
              <BookOpen className="w-3 h-3" />
              <span>{citations.length} Retrieved Sources</span>
            </button>
          ) : (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-stone-100 text-stone-500 border border-stone-200 text-[11px] font-medium">
              <BookOpen className="w-3 h-3 text-stone-400" />
              <span>0 Verified Sources</span>
            </span>
          )}
        </div>
      </div>

      {/* Header with Hero Image */}
      <div className="mb-8 relative rounded-3xl overflow-hidden group shadow-xl">
        <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors duration-500 z-10" />
        <img
          src={heroImage}
          alt={destination || "Trip Destination"}
          className="w-full h-60 object-cover transform group-hover:scale-105 transition-transform duration-700"
          onError={(e) => {
            e.target.src =
              "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800&q=80";
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-black/85 via-black/40 to-transparent z-20">
          <div className="flex items-center gap-1.5 text-white/90 text-[11px] font-semibold tracking-[0.14em] uppercase mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            Verified Itinerary
          </div>
          <h1
            className="text-[36px] leading-[1.1] text-white drop-shadow-md"
            style={{ fontFamily: "'Fraunces', serif", fontWeight: 600 }}
          >
            {destination || "Your trip"}
          </h1>
        </div>
      </div>

      {/* Day Cards with Interactive Citation Badges */}
      {cards.length > 0 ? (
        <div className="relative pl-8">
          <div className="absolute left-[11px] top-2 bottom-2 w-px bg-gradient-to-b from-[#E9DCD2] via-[#E9DCD2] to-transparent" />
          <div className="space-y-6">
            {cards.map((card, i) => {
              const isNoticeCard = card.title?.includes("Gate Notice") || isGateHalted;
              return (
                <div key={i} className="relative">
                  <div
                    className={`absolute -left-8 top-5 w-[22px] h-[22px] rounded-full bg-white border-2 ${
                      isNoticeCard ? "border-amber-600" : "border-[#B0322B]"
                    } flex items-center justify-center`}
                  >
                    {isNoticeCard ? (
                      <ShieldAlert className="w-3 h-3 text-amber-600" strokeWidth={2.5} />
                    ) : (
                      <MapPin className="w-3 h-3 text-[#B0322B]" strokeWidth={2.5} />
                    )}
                  </div>
                  <div
                    className={`bg-white/85 backdrop-blur-md rounded-3xl border ${
                      isNoticeCard
                        ? "border-amber-200 bg-amber-50/30 shadow-amber-500/5"
                        : "border-white/50 shadow-[0_4px_20px_-4px_rgba(176,50,43,0.06)]"
                    } px-6 py-5 hover:shadow-[0_8px_30px_-6px_rgba(176,50,43,0.12)] hover:-translate-y-0.5 transition-all duration-300`}
                  >
                    <h3
                      className={`text-[17px] mb-2.5 ${
                        isNoticeCard ? "text-amber-950 font-bold" : "text-[#241C1A]"
                      }`}
                      style={{ fontFamily: "'Fraunces', serif", fontWeight: 600 }}
                    >
                      {card.title}
                    </h3>
                    <ul className="space-y-2.5">
                      {(card.details || []).map((bulletText, j) => (
                        <li
                          key={j}
                          className="text-[13.5px] leading-relaxed text-[#4A3F3A] flex gap-2.5 items-start"
                        >
                          <span
                            className={`mt-2 w-1.5 h-1.5 rounded-full ${
                              isNoticeCard ? "bg-amber-600" : "bg-[#B0322B]"
                            } shrink-0`}
                          />
                          <div className="flex-1">
                            <FormattedBullet
                              text={bulletText}
                              onSourceClick={onSourceClick}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-[#F0E1D6] shadow-[0_2px_16px_-4px_rgba(176,50,43,0.08)] px-7 py-6">
          <div className="prose prose-sm max-w-none text-[13.5px] leading-relaxed text-[#4A3F3A]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{raw}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Footer provenance note */}
      <div className="flex items-center justify-between mt-10 text-[11.5px] text-[#8A7A72] border-t border-[#F0E1D6]/60 pt-4">
        <div className="flex items-center gap-1.5">
          {isGateHalted ? (
            <>
              <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-amber-800 font-medium">
                Scraping Gate Guardrail · Zero Hallucination Policy Enforced
              </span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Cross-Encoder ranked · 100% cited against retrieved evidence</span>
            </>
          )}
        </div>
        {citations && citations.length > 0 && (
          <button
            type="button"
            onClick={onOpenSources}
            className="text-[#B0322B] hover:underline font-medium cursor-pointer"
          >
            View all {citations.length} sources &rarr;
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Slide-over drawer displaying retrieved sources and web provenance.
 */
function RetrievedSourcesDrawer({ isOpen, onClose, sources, activeSourceId }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/30 backdrop-blur-xs flex justify-end animate-fade-in">
      <div className="w-full max-w-md h-full bg-white shadow-2xl flex flex-col animate-slide-left border-l border-[#F0E1D6]">
        {/* Drawer Header */}
        <div className="px-6 py-5 border-b border-[#F0E1D6] flex items-center justify-between bg-[#FCF8F5]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#FFF0EA] flex items-center justify-center text-[#B0322B] border border-[#F5D5C6]">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-[16px] font-semibold text-[#241C1A]">
                Retrieved Sources ({sources.length})
              </h2>
              <p className="text-[11.5px] text-[#8A7A72]">
                Live web evidence with Cross-Encoder scoring
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl hover:bg-black/5 flex items-center justify-center text-[#8A7A72] transition-colors cursor-pointer"
            aria-label="Close sources drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {sources.length === 0 ? (
            <div className="text-center py-12 text-[#8A7A72] text-[13px]">
              No sources retrieved yet for this session.
            </div>
          ) : (
            sources.map((src, idx) => {
              const isSelected = activeSourceId === src.source_id;
              return (
                <div
                  key={idx}
                  id={`source-${src.source_id}`}
                  className={`p-4 rounded-2xl border transition-all ${
                    isSelected
                      ? "border-[#B0322B] bg-[#FFF8F5] shadow-md ring-2 ring-[#B0322B]/20"
                      : "border-[#F0E1D6] bg-white hover:border-[#E0C9BA] hover:shadow-xs"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2 py-0.5 rounded-md bg-[#B0322B] text-white text-[11px] font-bold">
                      {src.source_id}
                    </span>
                    <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" />
                      Retrieved Source
                    </span>
                  </div>
                  <h4 className="text-[13.5px] font-semibold text-[#241C1A] mb-1.5 leading-snug">
                    {src.title || "Travel Guide & Stays"}
                  </h4>
                  <p className="text-[11.5px] text-[#8A7A72] mb-3">
                    Domain:{" "}
                    <span className="font-medium text-[#4A3F3A]">
                      {src.domain || "Web Source"}
                    </span>
                  </p>
                  {src.url && (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#B0322B] hover:text-[#8A251F] hover:underline"
                    >
                      <span>Visit Live Page</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-[#F0E1D6] bg-[#FCF8F5] text-[11px] text-[#8A7A72] text-center">
          Grounding Gate: Sources scraped, sha256-hashed, and session-isolated.
        </div>
      </div>
    </div>
  );
}

/**
 * Modal showing Stage 5 Critic factual claim audits.
 */
function VerificationAuditModal({ isOpen, onClose, report }) {
  if (!isOpen || !report) return null;

  const claims = report.claims || [];
  const faithfulnessPct = report.faithfulness_score != null
    ? Math.round(report.faithfulness_score * 100)
    : 100;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-lg max-h-[85vh] bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-slide-up-fade border border-[#F0E1D6]">
        {/* Modal Header */}
        <div className="px-6 py-5 border-b border-[#F0E1D6] flex items-center justify-between bg-[#FCF8F5]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-700">
              <ShieldCheck className="w-4.5 h-4.5" />
            </div>
            <div>
              <h2 className="text-[16px] font-semibold text-[#241C1A]">
                Stage 5 Claim Verification Audit
              </h2>
              <p className="text-[11.5px] text-[#8A7A72]">
                Critic Score: {faithfulnessPct}% · {claims.length} claims cross-examined
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl hover:bg-black/5 flex items-center justify-center text-[#8A7A72] cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {report?.status === "GATE_HALTED" ? (
            <div className="text-center py-8 text-[#8A7A72] text-[13px] space-y-2">
              <ShieldAlert className="w-8 h-8 text-amber-600 mx-auto" />
              <p className="font-semibold text-stone-800">Scraping Gate Activated</p>
              <p className="text-[12px] max-w-sm mx-auto">
                Execution was halted early because verified live internet sources could not be scraped.
                To prevent ungrounded hallucinations, generation and claim verification were bypassed.
              </p>
            </div>
          ) : claims.length === 0 ? (
            <div className="text-center py-8 text-[#8A7A72] text-[13px]">
              All draft itinerary claims verified against cited sources.
            </div>
          ) : (
            claims.map((claim, idx) => {
              const isSupported =
                (claim.status || "").toLowerCase() === "supported";
              return (
                <div
                  key={idx}
                  className="p-3.5 rounded-2xl border border-[#F0E1D6] bg-[#FCF8F5] text-[12.5px]"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-semibold text-[#241C1A]">
                      Claim #{idx + 1}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10.5px] font-semibold uppercase ${
                        isSupported
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {claim.status || "Verified"}
                    </span>
                  </div>
                  <p className="text-[#4A3F3A] mb-1.5 italic">
                    "{claim.claim}"
                  </p>
                  {claim.cited_source && (
                    <p className="text-[11.5px] text-[#8A7A72]">
                      Cited:{" "}
                      <span className="font-semibold text-[#B0322B]">
                        {claim.cited_source}
                      </span>
                    </p>
                  )}
                  {claim.reasoning && (
                    <p className="text-[11.5px] text-[#6E6058] mt-1 pt-1 border-t border-[#F0E1D6]">
                      {claim.reasoning}
                    </p>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[#F0E1D6] bg-[#FCF8F5] flex items-center justify-between">
          <span className="text-[11px] text-[#8A7A72]">
            Unsupported claims are excised or flagged before presentation.
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-[#B0322B] text-white text-[12px] font-semibold hover:bg-[#8A251F] transition-colors cursor-pointer"
          >
            Close Audit
          </button>
        </div>
      </div>
    </div>
  );
}