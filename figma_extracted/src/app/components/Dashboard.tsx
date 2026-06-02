import { useState, useEffect } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Textarea } from "./ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import {
  PlayCircle,
  DownloadSimple,
  QrCode,
  Circle,
  WarningCircle,
  CheckCircle,
  FilmSlate,
  SpinnerGap,
  BookOpen,
  TrendUp,
  Fire,
  BookBookmark,
  MapPin,
  UploadSimple,
  CalendarCheck,
  Copy,
  X,
  ChatCircle
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

type JobStatus = "queued" | "running" | "done" | "failed";
type JobStage = "시작" | "서지조회" | "대본생성" | "TTS 음성합성" | "자막정렬" | "비디오렌더링" | "완료";

interface Job {
  id: string;
  isbn: string;
  title: string;
  author?: string;
  status: JobStatus;
  stage: JobStage;
  createdAt: Date;
  videoPath?: string;
  qrPath?: string;
  error?: string;
  description?: string;
  pinnedComment?: string;
  tags?: string;
}

interface CurationBook {
  isbn: string;
  title: string;
  author: string;
  type: "A" | "B" | "C";
  reason: string;
}

const REGION_NAMES: Record<string, string> = {
  "11": "서울특별시",
  "26": "부산광역시",
  "27": "대구광역시",
  "28": "인천광역시",
  "29": "광주광역시",
  "30": "대전광역시",
};

export default function Dashboard() {
  const [isbn, setIsbn] = useState("");
  const [summary, setSummary] = useState("");
  const [keywords, setKeywords] = useState("");
  const [curationRegion, setCurationRegion] = useState("11"); // 큐레이션 탭 전용 지역 선택
  const [perType, setPerType] = useState(2); // 타입별 선정 수 (더보기 시 증가)
  const [jobs, setJobs] = useState<Job[]>([]);
  const [curationBooks, setCurationBooks] = useState<CurationBook[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCurationLoading, setIsCurationLoading] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<Job | null>(null);
  const [activeTab, setActiveTab] = useState<"queue" | "curation" | "location">("queue");
  const [nextSchedule, setNextSchedule] = useState<Date>(new Date(Date.now() + 86400000 * 2));
  const [apiError, setApiError] = useState(false);
  const [selectedJobForMeta, setSelectedJobForMeta] = useState<Job | null>(null);
  const [hoveredFailedJob, setHoveredFailedJob] = useState<string | null>(null);

  // 실시간 API jobs 목록 로드 및 주기적 갱신
  const fetchJobs = async () => {
    try {
      const response = await fetch('/api/jobs');
      if (response.ok) {
        const data = await response.json();
        
        // 데이터 매핑
        const mappedJobs = data.map((job: any) => {
          const titleNoSpaces = (job.title || "새로운 도서").replace(/\s+/g, '');
          
          const description = `📚 ${job.title || "새로운 도서"}
  
이 책이 궁금하다면 가까운 도서관에서 빌려보세요!
QR코드를 스캔하면 가장 가까운 소장 도서관을 찾을 수 있습니다.
  
🏛️ 도서관 정보나루 연계 서비스
📍 지역 맞춤형 도서 추천
  
#숏폼 #북트레일러 #도서관 #${(job.title || "책추천").substring(0, 10)} #책추천`;
  
          const pinnedComment = `✨ 이 영상이 마음에 드셨다면 좋아요와 구독 부탁드립니다!
  
📖 책 제목: ${job.title || "새로운 도서"}
🏛️ 우리 동네 도서관에서 만나보세요
  
#${titleNoSpaces} #도서관 #책추천`;
  
          const tags = [
            job.title,
            '북트레일러',
            '책추천',
            '도서관',
            '숏폼',
            '책소개',
            '독서'
          ].filter(Boolean).join(', ');

          return {
            id: job.id,
            isbn: job.isbn,
            title: job.title || "새로운 도서",
            author: job.author || "",
            status: job.status,
            stage: job.stage,
            createdAt: new Date(job.created_at * 1000),
            videoPath: job.video_path ? `/video/${job.id}` : undefined,
            qrPath: `/outputs/${job.isbn}_qr.png`,
            description,
            pinnedComment,
            tags
          };
        });

        setJobs(mappedJobs);
      }
    } catch (err) {
      console.error("Error fetching jobs:", err);
    }
  };

  // 큐레이션 데이터 API 로드
  const fetchCuration = async () => {
    setIsCurationLoading(true);
    try {
      const poolSize = perType * 6; // 타입별 선정 수에 비례해서 후보 풀도 확장
      const response = await fetch(`/api/curation?region=${curationRegion}&per_type=${perType}&pool_size=${poolSize}`);
      if (response.ok) {
        const data = await response.json();
        const list: CurationBook[] = [];
        
        const typeLabels: Record<string, "A" | "B" | "C"> = {
          "A_숨은명저": "A",
          "B_회전율개선": "B",
          "C_화제도서": "C"
        };

        for (let key in typeLabels) {
          const books = data[key] || [];
          books.forEach((b: any) => {
            list.push({
              isbn: b.isbn,
              title: b.title,
              author: b.author || "저자 미상",
              type: typeLabels[key],
              reason: b.reason
            });
          });
        }
        setCurationBooks(list);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsCurationLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000); // 3초 주기 자동 폴링
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchCuration();
  }, [curationRegion, perType]);

  const handleGenerate = async () => {
    if (!isbn) {
      toast.error("ISBN을 입력해주세요");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          isbn: isbn,
          region: "11", // default 서울
          custom_description: summary || null,
          custom_keywords: keywords || null
        })
      });

      const data = await response.json();
      if (response.ok) {
        toast.success(`${isbn} 북트레일러가 성공적으로 예약되었습니다!`);
        setIsbn("");
        setSummary("");
        setKeywords("");
        fetchJobs(); // 갱신
      } else {
        toast.error(`오류: ${data.detail || '요청 실패'}`);
      }
    } catch (err) {
      console.error(err);
      toast.error("서버 통신 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddToQueue = async (book: CurationBook) => {
    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isbn: book.isbn, region: curationRegion })
      });
      if (response.ok) {
        toast.success(`${book.title}이(가) 큐에 추가되었습니다`);
        fetchJobs();
      } else {
        toast.error("큐 추가 실패");
      }
    } catch (err) {
      toast.error("서버 통신 실패");
    }
  };

  const handleCSVUpload = (type: "solomon" | "trend") => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".csv";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        toast.success(`${type === "solomon" ? "솔로몬 장서 분석" : "트렌드 큐레이션"} CSV가 업로드되었습니다`);
        // 실제 구현에서는 파일을 파싱하여 처리
      }
    };
    input.click();
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success(`${label}이(가) 복사되었습니다`);
    });
  };

  const getStatusColor = (status: JobStatus) => {
    switch (status) {
      case "queued": return "bg-[rgba(156,163,175,0.12)] text-[#9ca3af] border-[rgba(156,163,175,0.20)]";
      case "running": return "bg-[rgba(212,162,76,0.15)] text-[#d4a24c] border-[rgba(212,162,76,0.30)] animate-pulse";
      case "done": return "bg-[rgba(45,106,79,0.15)] text-[#2d6a4f] border-[rgba(45,106,79,0.30)]";
      case "failed": return "bg-[rgba(155,28,28,0.15)] text-[#9b1c1c] border-[rgba(155,28,28,0.30)]";
    }
  };

  const getStatusIcon = (status: JobStatus) => {
    switch (status) {
      case "running": return <SpinnerGap className="animate-spin" size={16} />;
      case "done": return <CheckCircle size={16} />;
      case "failed": return <WarningCircle size={16} />;
      default: return null;
    }
  };

  const getTypeIcon = (type: "A" | "B" | "C") => {
    switch (type) {
      case "A": return <BookOpen size={20} weight="fill" className="text-[#d4a24c]" />;
      case "B": return <TrendUp size={20} weight="fill" className="text-[#b7791f]" />;
      case "C": return <Fire size={20} weight="fill" className="text-[#8b2635]" />;
    }
  };

  const getTypeLabel = (type: "A" | "B" | "C") => {
    switch (type) {
      case "A": return "숨은 명저";
      case "B": return "회전율 개선";
      case "C": return "화제 도서";
    }
  };

  const stats = {
    running: jobs.filter(j => j.status === "running").length,
    done: jobs.filter(j => j.status === "done").length,
    failed: jobs.filter(j => j.status === "failed").length,
  };

  return (
    <div className="min-h-screen dark" style={{
      background: '#1a0f0a',
      backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 400 400\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' /%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\' opacity=\'0.04\'/%3E%3C/svg%3E")',
    }}>
      {/* Header - Section A */}
      <header className="sticky top-0 z-50 border-b backdrop-blur-xl" style={{
        borderColor: 'rgba(212, 162, 76, 0.12)',
        background: 'rgba(26, 15, 10, 0.80)'
      }}>
        <div className="max-w-[1440px] mx-auto px-10 py-5 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{
              background: 'linear-gradient(135deg, #d4a24c 0%, #c8962a 100%)',
              boxShadow: '0 0 18px rgba(212, 162, 76, 0.22)'
            }}>
              <FilmSlate size={28} weight="bold" style={{ color: '#1a0f0a' }} />
            </div>
            <div>
              <h1 style={{
                fontFamily: '"Playfair Display", serif',
                fontSize: '1.5rem',
                fontWeight: 700,
                color: '#f5f0e8'
              }}>Local Book-Tik Factory</h1>
              <p style={{ fontSize: '0.75rem', color: 'rgba(245, 240, 232, 0.60)' }}>
                AI 기반 숏폼 북트레일러 자동 생성 통제 센터
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{
              background: 'rgba(212, 162, 76, 0.08)',
              border: '1px solid rgba(212, 162, 76, 0.15)'
            }}>
              <CalendarCheck size={16} style={{ color: '#d4a24c' }} />
              <span style={{ fontSize: '0.75rem', color: 'rgba(245, 240, 232, 0.70)' }}>
                다음 자동 실행: {nextSchedule.toLocaleDateString('ko-KR')} 월요일
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Circle size={8} weight="fill" className="text-[#2d6a4f] animate-pulse" />
              <span style={{ fontSize: '0.875rem', color: 'rgba(245, 240, 232, 0.60)' }}>
                통제 서버 작동 중 (온라인)
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-[1440px] mx-auto px-10 py-8 grid grid-cols-12 gap-6">
        {/* Left Panel - Section B */}
        <div className="col-span-4 space-y-6">
          {/* 현황 요약 카드 */}
          <Card className="p-6 border-0 rounded-[14px]" style={{
            background: '#2c1810',
            boxShadow: '0 8px 24px rgba(212, 162, 76, 0.08)'
          }}>
            <h3 style={{
              fontFamily: '"Noto Serif KR", serif',
              fontSize: '1rem',
              fontWeight: 700,
              color: '#f5f0e8',
              marginBottom: '1.5rem'
            }}>현황 요약</h3>

            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-4 rounded-lg" style={{
                background: 'rgba(212, 162, 76, 0.08)',
                border: '1px solid rgba(212, 162, 76, 0.15)'
              }}>
                <div style={{
                  fontFamily: '"Playfair Display", serif',
                  fontSize: '2rem',
                  fontWeight: 700,
                  background: 'linear-gradient(135deg, #d4a24c, #e0b05e)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  marginBottom: '0.25rem'
                }}>{stats.running}</div>
                <div style={{ fontSize: '0.75rem', color: 'rgba(245, 240, 232, 0.60)' }}>진행 작업</div>
              </div>

              <div className="text-center p-4 rounded-lg" style={{
                background: 'rgba(45, 106, 79, 0.08)',
                border: '1px solid rgba(45, 106, 79, 0.15)'
              }}>
                <div style={{
                  fontFamily: '"Playfair Display", serif',
                  fontSize: '2rem',
                  fontWeight: 700,
                  color: '#2d6a4f',
                  marginBottom: '0.25rem'
                }}>{stats.done}</div>
                <div style={{ fontSize: '0.75rem', color: 'rgba(245, 240, 232, 0.60)' }}>제작 완료</div>
              </div>

              <div className="text-center p-4 rounded-lg" style={{
                background: 'rgba(155, 28, 28, 0.08)',
                border: '1px solid rgba(155, 28, 28, 0.15)'
              }}>
                <div style={{
                  fontFamily: '"Playfair Display", serif',
                  fontSize: '2rem',
                  fontWeight: 700,
                  color: '#9b1c1c',
                  marginBottom: '0.25rem'
                }}>{stats.failed}</div>
                <div style={{ fontSize: '0.75rem', color: 'rgba(245, 240, 232, 0.60)' }}>오류 실패</div>
              </div>
            </div>
          </Card>

          {/* 숏폼 수동 생성 요청 카드 */}
          <Card className="p-6 border-0 rounded-[14px]" style={{
            background: '#2c1810',
            boxShadow: '0 8px 24px rgba(212, 162, 76, 0.08)'
          }}>
            <h2 style={{
              fontFamily: '"Noto Serif KR", serif',
              fontSize: '1.125rem',
              fontWeight: 700,
              color: '#f5f0e8',
              marginBottom: '1.5rem'
            }}>숏폼 수동 생성 요청</h2>

            <div className="space-y-4">
              <div>
                <Label htmlFor="isbn" style={{
                  fontSize: '0.875rem',
                  color: '#f5f0e8',
                  marginBottom: '0.5rem',
                  display: 'block'
                }}>ISBN-13</Label>
                <Input
                  id="isbn"
                  placeholder="예: 9788937473135"
                  maxLength={13}
                  value={isbn}
                  onChange={(e) => setIsbn(e.target.value)}
                  className="border rounded-lg h-11 font-mono"
                  style={{
                    background: 'rgba(245, 240, 232, 0.04)',
                    borderColor: 'rgba(212, 162, 76, 0.12)',
                    color: '#f5f0e8',
                    borderRadius: '8px'
                  }}
                />
              </div>

              <div>
                <Label htmlFor="summary" style={{
                  fontSize: '0.875rem',
                  color: '#f5f0e8',
                  marginBottom: '0.5rem',
                  display: 'block'
                }}>한 줄 줄거리 (선택)</Label>
                <Textarea
                  id="summary"
                  placeholder="LOD에 소개가 없는 경우 직접 요약을 적어주세요"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  className="border rounded-lg min-h-[80px] resize-none"
                  style={{
                    background: 'rgba(245, 240, 232, 0.04)',
                    borderColor: 'rgba(212, 162, 76, 0.12)',
                    color: '#f5f0e8',
                    borderRadius: '8px'
                  }}
                />
              </div>

              <div>
                <Label htmlFor="keywords" style={{
                  fontSize: '0.875rem',
                  color: '#f5f0e8',
                  marginBottom: '0.5rem',
                  display: 'block'
                }}>추천 키워드 (선택)</Label>
                <Input
                  id="keywords"
                  placeholder="예: AI, 미래기술, 한국소설"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  className="border rounded-lg h-11"
                  style={{
                    background: 'rgba(245, 240, 232, 0.04)',
                    borderColor: 'rgba(212, 162, 76, 0.12)',
                    color: '#f5f0e8',
                    borderRadius: '8px'
                  }}
                />
              </div>

              <Button
                onClick={handleGenerate}
                disabled={isLoading}
                className="w-full h-12 font-semibold rounded-lg border-0 transition-all"
                style={{
                  background: isLoading ? 'rgba(212, 162, 76, 0.60)' : '#d4a24c',
                  color: '#1a0f0a',
                  boxShadow: isLoading ? 'none' : '0 0 18px rgba(212, 162, 76, 0.22)',
                  borderRadius: '8px'
                }}
              >
                {isLoading ? (
                  <>
                    <SpinnerGap className="animate-spin mr-2" size={20} />
                    요청 중...
                  </>
                ) : (
                  "북트레일러 생성 큐 예약"
                )}
              </Button>
            </div>
          </Card>

          {/* 데이터 업로드 카드 */}
          <Card className="p-6 border-0 rounded-[14px]" style={{
            background: '#2c1810',
            boxShadow: '0 8px 24px rgba(212, 162, 76, 0.08)'
          }}>
            <h3 style={{
              fontFamily: '"Noto Serif KR", serif',
              fontSize: '1rem',
              fontWeight: 700,
              color: '#f5f0e8',
              marginBottom: '1rem'
            }}>데이터 업로드</h3>

            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => handleCSVUpload("solomon")}
                style={{
                  borderColor: 'rgba(212, 162, 76, 0.20)',
                  color: 'rgba(245, 240, 232, 0.70)',
                  background: 'rgba(245, 240, 232, 0.02)'
                }}
              >
                <UploadSimple size={18} className="mr-2" />
                솔로몬 장서 분석 CSV
              </Button>

              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => handleCSVUpload("trend")}
                style={{
                  borderColor: 'rgba(212, 162, 76, 0.20)',
                  color: 'rgba(245, 240, 232, 0.70)',
                  background: 'rgba(245, 240, 232, 0.02)'
                }}
              >
                <UploadSimple size={18} className="mr-2" />
                트렌드 큐레이션 CSV
              </Button>
            </div>

            <p style={{
              fontSize: '0.75rem',
              color: 'rgba(245, 240, 232, 0.40)',
              marginTop: '1rem',
              lineHeight: 1.5
            }}>
              선택적 입력: 솔로몬 장서 평가 및 북튜브·북톡 화제작 리스트를 업로드하여 큐레이션을 고도화할 수 있습니다.
            </p>
          </Card>
        </div>

        {/* Right Panel - Section C with Tabs */}
        <div className="col-span-8">
          <Card className="border-0 rounded-[14px]" style={{
            background: '#2c1810',
            boxShadow: '0 8px 24px rgba(212, 162, 76, 0.08)'
          }}>
            {/* Tab Navigation */}
            <div className="flex items-center gap-1 px-6 pt-6 pb-4" style={{
              borderBottom: '1px solid rgba(212, 162, 76, 0.08)'
            }}>
              <button
                onClick={() => setActiveTab("queue")}
                className="px-4 py-2 rounded-lg transition-all"
                style={{
                  background: activeTab === "queue" ? 'rgba(212, 162, 76, 0.15)' : 'transparent',
                  color: activeTab === "queue" ? '#d4a24c' : 'rgba(245, 240, 232, 0.60)',
                  border: activeTab === "queue" ? '1px solid rgba(212, 162, 76, 0.30)' : '1px solid transparent',
                  fontWeight: activeTab === "queue" ? 600 : 400,
                  fontSize: '0.9375rem'
                }}
              >
                실시간 대기열
              </button>
              <button
                onClick={() => setActiveTab("curation")}
                className="px-4 py-2 rounded-lg transition-all"
                style={{
                  background: activeTab === "curation" ? 'rgba(212, 162, 76, 0.15)' : 'transparent',
                  color: activeTab === "curation" ? '#d4a24c' : 'rgba(245, 240, 232, 0.60)',
                  border: activeTab === "curation" ? '1px solid rgba(212, 162, 76, 0.30)' : '1px solid transparent',
                  fontWeight: activeTab === "curation" ? 600 : 400,
                  fontSize: '0.9375rem'
                }}
              >
                주간 큐레이션
              </button>
              <button
                onClick={() => setActiveTab("location")}
                className="px-4 py-2 rounded-lg transition-all"
                style={{
                  background: activeTab === "location" ? 'rgba(212, 162, 76, 0.15)' : 'transparent',
                  color: activeTab === "location" ? '#d4a24c' : 'rgba(245, 240, 232, 0.60)',
                  border: activeTab === "location" ? '1px solid rgba(212, 162, 76, 0.30)' : '1px solid transparent',
                  fontWeight: activeTab === "location" ? 600 : 400,
                  fontSize: '0.9375rem'
                }}
              >
                위치 안내 미리보기
              </button>
            </div>

            {/* Tab Content */}
            <div className="p-6">
              {/* Queue Tab */}
              {activeTab === "queue" && (
                <>
                  <h2 style={{
                    fontFamily: '"Noto Serif KR", serif',
                    fontSize: '1.125rem',
                    fontWeight: 700,
                    color: '#f5f0e8',
                    marginBottom: '1.5rem'
                  }}>실시간 생성 대기열 모니터</h2>

                  {/* API Error Banner */}
                  {apiError && (
                    <div className="mb-4 p-4 rounded-lg flex items-center justify-between" style={{
                      background: 'rgba(239, 68, 68, 0.10)',
                      borderLeft: '4px solid #ef4444',
                      borderRadius: '10px'
                    }}>
                      <div className="flex items-center gap-3">
                        <WarningCircle size={20} style={{ color: '#ef4444' }} />
                        <span style={{ fontSize: '0.875rem', color: '#f5f0e8' }}>
                          데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
                        </span>
                      </div>
                      <button
                        onClick={() => {
                          setApiError(false);
                          toast.success("다시 시도 중...");
                        }}
                        style={{
                          fontSize: '0.875rem',
                          color: '#ef4444',
                          textDecoration: 'underline',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer'
                        }}
                      >
                        재시도 →
                      </button>
                    </div>
                  )}

            {jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <FilmSlate size={72} style={{ color: '#d4a24c', opacity: 0.25, marginBottom: '1rem' }} />
                <h3 style={{
                  fontSize: '1rem',
                  fontWeight: 600,
                  color: '#f5f0e8',
                  marginBottom: '0.5rem'
                }}>아직 생성된 북트레일러가 없습니다</h3>
                <p style={{
                  fontSize: '0.875rem',
                  color: 'rgba(245, 240, 232, 0.60)',
                  marginBottom: '1.5rem',
                  maxWidth: '28rem'
                }}>
                  왼쪽 패널에서 ISBN을 입력하거나<br/>
                  주간 큐레이션을 예약해 보세요.
                </p>
                <Button
                  variant="outline"
                  className="border rounded-lg"
                  style={{
                    borderColor: 'rgba(212, 162, 76, 0.50)',
                    color: '#d4a24c',
                    background: 'transparent',
                    borderRadius: '8px'
                  }}
                >
                  지금 생성 시작하기
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => {
                  const stages: JobStage[] = ["시작", "서지조회", "대본생성", "TTS 음성합성", "자막정렬", "비디오렌더링", "완료"];

                  return (
                    <div
                      key={job.id}
                      className="p-4 rounded-lg transition-all relative"
                      style={{
                        background: 'rgba(245, 240, 232, 0.02)',
                        border: '1px solid rgba(245, 240, 232, 0.05)',
                        borderRadius: '8px'
                      }}
                      onMouseEnter={() => job.status === "failed" && setHoveredFailedJob(job.id)}
                      onMouseLeave={() => setHoveredFailedJob(null)}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="relative">
                            <Badge className={cn("text-xs font-medium border px-2 py-1 rounded", getStatusColor(job.status))}>
                              <span className="flex items-center gap-1.5">
                                {getStatusIcon(job.status)}
                                {job.status === "queued" && "대기"}
                                {job.status === "running" && "생성 중"}
                                {job.status === "done" && "완료"}
                                {job.status === "failed" && "실패"}
                              </span>
                            </Badge>

                            {/* Failed Job Tooltip */}
                            {job.status === "failed" && hoveredFailedJob === job.id && (
                              <div
                                className="absolute z-50 px-3 py-2 rounded-lg whitespace-pre-line"
                                style={{
                                  background: 'rgba(17, 24, 39, 0.95)',
                                  color: '#fff',
                                  fontSize: '0.75rem',
                                  maxWidth: '240px',
                                  bottom: '100%',
                                  left: '50%',
                                  transform: 'translateX(-50%) translateY(-8px)',
                                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
                                }}
                              >
                                {job.error || "알 수 없는 오류가 발생했습니다"}
                              </div>
                            )}
                          </div>
                          <span style={{
                            fontFamily: '"Noto Serif KR", serif',
                            fontWeight: 700,
                            fontSize: '1rem',
                            color: '#f5f0e8'
                          }}>{job.title}</span>
                        </div>

                        {job.status === "done" && (
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setSelectedVideo(job)}
                              style={{ color: '#d4a24c' }}
                            >
                              <PlayCircle size={20} className="mr-1.5" />
                              미리보기
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setSelectedJobForMeta(job)}
                              style={{ color: '#10b981' }}
                            >
                              <ChatCircle size={20} className="mr-1.5" />
                              유튜브 설명
                            </Button>
                            <a href={job.videoPath} download={`${job.isbn}_trailer.mp4`}>
                              <Button
                                size="sm"
                                variant="ghost"
                                style={{ color: 'rgba(245, 240, 232, 0.60)' }}
                              >
                                <DownloadSimple size={20} className="mr-1.5" />
                                MP4
                              </Button>
                            </a>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => window.open(job.qrPath, '_blank')}
                              style={{ color: 'rgba(245, 240, 232, 0.60)' }}
                            >
                              <QrCode size={20} className="mr-1.5" />
                              QR
                            </Button>
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-6" style={{
                        fontSize: '0.75rem',
                        color: 'rgba(245, 240, 232, 0.40)'
                      }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                          Job ID: {job.id}
                        </span>
                        <span>•</span>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                          ISBN: {job.isbn}
                        </span>
                        <span>•</span>
                        <span>{job.createdAt.toLocaleTimeString("ko-KR")}</span>
                      </div>

                      {job.status === "running" && (
                        <div className="mt-3 flex items-center gap-2" style={{
                          fontSize: '0.8125rem',
                          color: '#d4a24c'
                        }}>
                          <span style={{ color: 'rgba(245, 240, 232, 0.40)' }}>현재 단계:</span>
                          <span className="font-medium flex items-center gap-2">
                            {stages.map((stage, idx) => (
                              <span key={stage} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span
                                  className={job.stage === stage ? "px-2 py-0.5 rounded" : ""}
                                  style={
                                    job.stage === stage ? {
                                      background: 'rgba(212, 162, 76, 0.20)',
                                      border: '1px solid rgba(212, 162, 76, 0.40)',
                                      opacity: 1
                                    } : {
                                      opacity: 0.5
                                    }
                                  }
                                >
                                  {stage}
                                </span>
                                {idx < stages.length - 1 && (
                                  <span style={{ opacity: 0.3 }}>›</span>
                                )}
                              </span>
                            ))}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
                </>
              )}

              {/* Curation Tab */}
              {activeTab === "curation" && (
                <>
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 style={{
                        fontFamily: '"Noto Serif KR", serif',
                        fontSize: '1.125rem',
                        fontWeight: 700,
                        color: '#f5f0e8',
                        marginBottom: '0.25rem'
                      }}>주간 큐레이션 도서 목록</h2>
                      <p style={{
                        fontSize: '0.875rem',
                        color: 'rgba(245, 240, 232, 0.60)'
                      }}>
                        총 {curationBooks.length}권 선정 • 타입별 자동 분류
                      </p>
                    </div>

                    <Select value={curationRegion} onValueChange={setCurationRegion}>
                      <SelectTrigger
                        className="border rounded-lg h-10 w-[180px]"
                        style={{
                          background: 'rgba(245, 240, 232, 0.04)',
                          borderColor: 'rgba(212, 162, 76, 0.12)',
                          color: '#f5f0e8',
                          borderRadius: '8px'
                        }}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent
                        className="border-0"
                        style={{
                          background: '#2c1810',
                          borderColor: 'rgba(212, 162, 76, 0.20)',
                          color: '#f5f0e8'
                        }}
                      >
                        {Object.entries(REGION_NAMES).map(([code, name]) => (
                          <SelectItem
                            key={code}
                            value={code}
                            style={{
                              color: '#f5f0e8'
                            }}
                          >{name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* 타입 범례 */}
                  <div className="flex items-center gap-6 mb-4 px-4 py-3 rounded-lg" style={{
                    background: 'rgba(212, 162, 76, 0.05)',
                    border: '1px solid rgba(212, 162, 76, 0.10)'
                  }}>
                    <div className="flex items-center gap-2">
                      <BookOpen size={16} weight="fill" className="text-[#d4a24c]" />
                      <span style={{ fontSize: '0.8125rem', color: 'rgba(245, 240, 232, 0.70)' }}>
                        타입 A: 솔로몬 평가 우수, 대출 저조 (숨은 명저)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendUp size={16} weight="fill" className="text-[#b7791f]" />
                      <span style={{ fontSize: '0.8125rem', color: 'rgba(245, 240, 232, 0.70)' }}>
                        타입 B: 소장 대비 대출 저조 (회전율 개선)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Fire size={16} weight="fill" className="text-[#8b2635]" />
                      <span style={{ fontSize: '0.8125rem', color: 'rgba(245, 240, 232, 0.70)' }}>
                        타입 C: 쇼츠·SNS 화제, 대출 급상승
                      </span>
                    </div>
                  </div>

                  {isCurationLoading ? (
                    <div className="flex flex-col items-center justify-center py-16">
                      <SpinnerGap className="animate-spin mb-4" size={40} style={{ color: '#d4a24c' }} />
                      <p style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#f5f0e8', marginBottom: '0.25rem' }}>
                        큐레이션 도서를 분석하고 있습니다
                      </p>
                      <p style={{ fontSize: '0.8125rem', color: 'rgba(245, 240, 232, 0.50)' }}>
                        정보나루 API에서 타입별 {perType}권씩 선정 중...
                      </p>
                    </div>
                  ) : (
                  <div
                    className="space-y-3 pr-2"
                    style={{
                      maxHeight: '550px',
                      overflowY: 'auto',
                      scrollbarWidth: 'thin',
                      scrollbarColor: 'rgba(212, 162, 76, 0.30) rgba(245, 240, 232, 0.05)'
                    }}
                  >
                    {curationBooks.map((book) => (
                      <div
                        key={book.isbn}
                        className="p-5 rounded-lg transition-all hover:bg-[rgba(245,240,232,0.04)] cursor-pointer"
                        style={{
                          background: 'rgba(245, 240, 232, 0.02)',
                          border: '1px solid rgba(212, 162, 76, 0.10)'
                        }}
                      >
                        <div className="flex items-start gap-4 mb-3">
                          <div className="flex-shrink-0 mt-1">
                            {getTypeIcon(book.type)}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <Badge className="text-xs px-2 py-1" style={{
                                background: 'rgba(212, 162, 76, 0.15)',
                                color: '#d4a24c',
                                border: 'none'
                              }}>
                                타입 {book.type}
                              </Badge>
                              <span style={{
                                fontSize: '0.75rem',
                                color: 'rgba(245, 240, 232, 0.60)'
                              }}>{getTypeLabel(book.type)}</span>
                            </div>
                            <div style={{
                              fontFamily: '"Noto Serif KR", serif',
                              fontWeight: 700,
                              fontSize: '1.0625rem',
                              color: '#f5f0e8',
                              marginBottom: '0.375rem'
                            }}>{book.title}</div>
                            <div style={{
                              fontSize: '0.8125rem',
                              color: 'rgba(245, 240, 232, 0.50)',
                              marginBottom: '0.75rem'
                            }}>{book.author}</div>
                            <div style={{
                              fontSize: '0.875rem',
                              color: 'rgba(245, 240, 232, 0.70)',
                              lineHeight: 1.6,
                              paddingLeft: '1rem',
                              borderLeft: '2px solid rgba(212, 162, 76, 0.20)'
                            }}>
                              {book.reason}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between pt-3" style={{
                          borderTop: '1px solid rgba(245, 240, 232, 0.05)'
                        }}>
                          <span style={{
                            fontFamily: 'JetBrains Mono, monospace',
                            fontSize: '0.75rem',
                            color: 'rgba(245, 240, 232, 0.40)'
                          }}>ISBN: {book.isbn}</span>
                          <Button
                            size="sm"
                            onClick={() => handleAddToQueue(book)}
                            style={{
                              background: 'rgba(212, 162, 76, 0.15)',
                              color: '#d4a24c',
                              fontSize: '0.8125rem',
                              border: '1px solid rgba(212, 162, 76, 0.25)'
                            }}
                          >
                            큐에 추가
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                  )}

                  {/* 더보기 / 줄이기 버튼 */}
                  <div className="flex items-center justify-center gap-3 mt-4 pt-4" style={{
                    borderTop: '1px solid rgba(212, 162, 76, 0.08)'
                  }}>
                    {perType > 2 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPerType(2)}
                        className="rounded-lg"
                        style={{
                          borderColor: 'rgba(245, 240, 232, 0.15)',
                          color: 'rgba(245, 240, 232, 0.60)',
                          background: 'transparent'
                        }}
                      >
                        기본으로 줄이기
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPerType(prev => prev + 2)}
                      className="rounded-lg"
                      style={{
                        borderColor: 'rgba(212, 162, 76, 0.30)',
                        color: '#d4a24c',
                        background: 'rgba(212, 162, 76, 0.08)'
                      }}
                    >
                      더 많은 도서 불러오기 (타입별 +2권)
                    </Button>
                  </div>

                  <p style={{
                    fontSize: '0.75rem',
                    color: 'rgba(245, 240, 232, 0.35)',
                    textAlign: 'center',
                    marginTop: '0.5rem'
                  }}>
                    현재 타입별 {perType}권씩 선정 중
                  </p>
                </>
              )}

              {/* Location Tab */}
              {activeTab === "location" && (
                <>
                  <div className="mb-6">
                    <h2 style={{
                      fontFamily: '"Noto Serif KR", serif',
                      fontSize: '1.125rem',
                      fontWeight: 700,
                      color: '#f5f0e8',
                      marginBottom: '0.25rem'
                    }}>위치 안내 미리보기</h2>
                    <p style={{
                      fontSize: '0.875rem',
                      color: 'rgba(245, 240, 232, 0.60)'
                    }}>QR 스캔 후 시민들이 보게 될 화면입니다</p>
                  </div>

                  <div className="flex justify-center">
                    <div className="w-[375px] rounded-2xl overflow-hidden" style={{
                      boxShadow: '0 20px 60px rgba(0, 0, 0, 0.40)',
                      border: '8px solid #2c1810'
                    }}>
                      <div style={{ transform: 'scale(0.9)', transformOrigin: 'top center' }}>
                        <div className="bg-white" style={{ minHeight: '600px' }}>
                          {/* Mobile Preview Content */}
                          <div className="px-5 pt-8 pb-10" style={{
                            background: 'linear-gradient(135deg, #1f3d24 0%, #355e3b 100%)',
                            color: '#ffffff'
                          }}>
                            <div className="flex justify-center mb-4">
                              <div className="px-4 py-1.5 rounded-full" style={{
                                background: 'rgba(255, 255, 255, 0.15)',
                                border: '1px solid rgba(255, 255, 255, 0.25)',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                letterSpacing: '0.05em'
                              }}>BOOK-TIK LIBRARY FINDER</div>
                            </div>

                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <p style={{ fontSize: '0.8125rem', opacity: 0.80, marginBottom: '0.5rem' }}>
                                  숏폼에서 만난 책
                                </p>
                                <h1 style={{
                                  fontFamily: '"Noto Serif KR", serif',
                                  fontSize: '1.5rem',
                                  fontWeight: 700,
                                  marginBottom: '0.375rem',
                                  lineHeight: 1.3
                                }}>82년생 김지영</h1>
                                <p style={{ fontSize: '0.9375rem', opacity: 0.90 }}>조남주</p>
                              </div>
                              <BookBookmark size={40} weight="fill" />
                            </div>
                          </div>

                          <div className="px-5 py-6" style={{ background: '#faf7f2' }}>
                            <div className="mb-4 p-4 bg-white rounded-2xl text-center" style={{
                              boxShadow: '0 2px 12px rgba(44, 24, 16, 0.06)'
                            }}>
                              <Badge className="text-xs px-3 py-1.5" style={{
                                background: '#d1fae5',
                                color: '#065f46',
                                border: 'none'
                              }}>
                                <MapPin size={16} weight="fill" className="mr-1.5" />
                                내 위치 수신 완료
                              </Badge>
                            </div>

                            <h3 style={{
                              fontFamily: '"Noto Sans KR", sans-serif',
                              fontSize: '1rem',
                              fontWeight: 700,
                              color: '#2c1810',
                              marginBottom: '0.75rem'
                            }}>최단거리 소장 도서관</h3>

                            <div className="space-y-3">
                              <div className="p-4 bg-white rounded-2xl" style={{
                                border: '1px solid #e8e0d4',
                                boxShadow: '0 2px 12px rgba(44, 24, 16, 0.06)'
                              }}>
                                <div className="flex items-start justify-between mb-2">
                                  <span style={{
                                    fontWeight: 600,
                                    fontSize: '0.9375rem',
                                    color: '#2c1810'
                                  }}>서초구립 반포도서관</span>
                                  <Badge style={{
                                    background: 'rgba(53, 94, 59, 0.10)',
                                    color: '#355e3b',
                                    fontSize: '0.75rem',
                                    border: 'none'
                                  }}>
                                    850m
                                  </Badge>
                                </div>
                                <p style={{
                                  fontSize: '0.8125rem',
                                  color: 'rgba(44, 24, 16, 0.60)',
                                  marginBottom: '0.75rem'
                                }}>서울 서초구 반포대로 101</p>
                                <div className="flex items-center justify-between pt-2" style={{
                                  borderTop: '1px solid rgba(44, 24, 16, 0.08)'
                                }}>
                                  <span style={{
                                    fontSize: '0.75rem',
                                    color: '#2d6a4f',
                                    fontWeight: 500
                                  }}>대출 가능 • 소장: 3권</span>
                                  <span style={{
                                    fontSize: '0.8125rem',
                                    color: '#355e3b',
                                    fontWeight: 500
                                  }}>길찾기</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 p-4 rounded-lg" style={{
                    background: 'rgba(212, 162, 76, 0.08)',
                    border: '1px solid rgba(212, 162, 76, 0.15)'
                  }}>
                    <p style={{
                      fontSize: '0.875rem',
                      color: 'rgba(245, 240, 232, 0.70)',
                      lineHeight: 1.6
                    }}>
                      💡 이 화면은 생성된 숏폼 영상의 QR 코드를 시민들이 스캔했을 때 표시됩니다.
                      GPS 기반으로 가장 가까운 도서관을 자동으로 안내합니다.
                    </p>
                  </div>
                </>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Video Modal - Section D */}
      {selectedVideo && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-lg"
          style={{
            background: 'rgba(26, 15, 10, 0.90)'
          }}
          onClick={() => setSelectedVideo(null)}
        >
          <div
            className="relative max-h-[80vh] rounded-xl overflow-hidden shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setSelectedVideo(null)}
              className="absolute top-4 right-4 z-10 rounded-full"
              style={{
                background: 'rgba(0, 0, 0, 0.50)',
                color: '#f5f0e8',
                border: '1px solid rgba(245, 240, 232, 0.20)'
              }}
            >
              ✕
            </Button>

            <div className="bg-black aspect-[9/16] w-[360px]">
              {selectedVideo.videoPath ? (
                <video
                  className="w-full h-full object-contain"
                  src={selectedVideo.videoPath}
                  controls
                  autoPlay
                />
              ) : (
                <div className="flex items-center justify-center h-full" style={{ color: 'rgba(245, 240, 232, 0.40)' }}>
                  <div className="text-center">
                    <PlayCircle size={64} className="mx-auto mb-4 opacity-50" />
                    <p style={{ fontSize: '0.875rem' }}>영상을 불러올 수 없습니다</p>
                    <p style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>{selectedVideo.title}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 text-center" style={{ background: '#2c1810' }}>
              <p style={{
                fontFamily: '"Noto Serif KR", serif',
                fontWeight: 700,
                color: '#f5f0e8',
                marginBottom: '0.75rem'
              }}>{selectedVideo.title}</p>
              <a href={selectedVideo.videoPath} download={`${selectedVideo.isbn}_trailer.mp4`}>
                <Button className="rounded-lg" style={{
                  background: '#d4a24c',
                  color: '#1a0f0a',
                  borderRadius: '8px'
                }}>
                  <DownloadSimple size={20} className="mr-2" />
                  MP4 저장
                </Button>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* YouTube Metadata Modal */}
      {selectedJobForMeta && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-lg"
          style={{
            background: 'rgba(26, 15, 10, 0.90)'
          }}
          onClick={() => setSelectedJobForMeta(null)}
        >
          <div
            className="relative max-w-3xl w-full mx-4 rounded-xl overflow-hidden shadow-2xl"
            style={{ background: '#2c1810' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-6 border-b" style={{
              borderColor: 'rgba(212, 162, 76, 0.12)'
            }}>
              <h3 style={{
                fontFamily: '"Noto Serif KR", serif',
                fontSize: '1.25rem',
                fontWeight: 700,
                color: '#f5f0e8'
              }}>유튜브 업로드 정보</h3>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setSelectedJobForMeta(null)}
                style={{ color: 'rgba(245, 240, 232, 0.60)' }}
              >
                <X size={24} />
              </Button>
            </div>

            <div className="p-6 space-y-6">
              {/* 영상 설명 */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <Label style={{ color: '#f5f0e8', fontSize: '0.9375rem', fontWeight: 600 }}>
                    영상 설명
                  </Label>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(selectedJobForMeta.description || "", "영상 설명")}
                    style={{
                      borderColor: 'rgba(212, 162, 76, 0.30)',
                      color: '#d4a24c',
                      background: 'rgba(212, 162, 76, 0.08)'
                    }}
                  >
                    <Copy size={16} className="mr-1.5" />
                    복사
                  </Button>
                </div>
                <Textarea
                  readOnly
                  value={selectedJobForMeta.description || ""}
                  rows={8}
                  className="border rounded-lg font-mono text-sm resize-none"
                  style={{
                    background: 'rgba(245, 240, 232, 0.04)',
                    borderColor: 'rgba(212, 162, 76, 0.12)',
                    color: '#f5f0e8',
                    borderRadius: '8px'
                  }}
                />
              </div>

              {/* 고정 댓글 */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <Label style={{ color: '#f5f0e8', fontSize: '0.9375rem', fontWeight: 600 }}>
                    고정 댓글
                  </Label>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(selectedJobForMeta.pinnedComment || "", "고정 댓글")}
                    style={{
                      borderColor: 'rgba(212, 162, 76, 0.30)',
                      color: '#d4a24c',
                      background: 'rgba(212, 162, 76, 0.08)'
                    }}
                  >
                    <Copy size={16} className="mr-1.5" />
                    복사
                  </Button>
                </div>
                <Textarea
                  readOnly
                  value={selectedJobForMeta.pinnedComment || ""}
                  rows={6}
                  className="border rounded-lg font-mono text-sm resize-none"
                  style={{
                    background: 'rgba(245, 240, 232, 0.04)',
                    borderColor: 'rgba(212, 162, 76, 0.12)',
                    color: '#f5f0e8',
                    borderRadius: '8px'
                  }}
                />
              </div>

              {/* 태그 */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <Label style={{ color: '#f5f0e8', fontSize: '0.9375rem', fontWeight: 600 }}>
                    태그 (Tags)
                  </Label>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(selectedJobForMeta.tags || "", "태그")}
                    style={{
                      borderColor: 'rgba(212, 162, 76, 0.30)',
                      color: '#d4a24c',
                      background: 'rgba(212, 162, 76, 0.08)'
                    }}
                  >
                    <Copy size={16} className="mr-1.5" />
                    복사
                  </Button>
                </div>
                <Textarea
                  readOnly
                  value={selectedJobForMeta.tags || ""}
                  rows={3}
                  className="border rounded-lg font-mono text-sm resize-none"
                  style={{
                    background: 'rgba(245, 240, 232, 0.04)',
                    borderColor: 'rgba(212, 162, 76, 0.12)',
                    color: '#f5f0e8',
                    borderRadius: '8px'
                  }}
                />
              </div>

              <div className="p-3 rounded-lg" style={{
                background: 'rgba(212, 162, 76, 0.08)',
                border: '1px solid rgba(212, 162, 76, 0.15)'
              }}>
                <p style={{
                  fontSize: '0.8125rem',
                  color: 'rgba(245, 240, 232, 0.70)',
                  lineHeight: 1.5
                }}>
                  💡 각 복사 버튼을 클릭하여 유튜브 업로드 시 사용할 수 있습니다. 태그는 쉼표로 구분되어 있습니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
