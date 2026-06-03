import { useState, useEffect } from "react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import {
  MapPin,
  NavigationArrow,
  SpinnerGap,
  GlobeHemisphereWest,
  BookBookmark
} from "@phosphor-icons/react";

interface Library {
  name: string;
  address: string;
  distance: number;
  available: boolean;
  stock: number;
}

type GpsStatus = "loading" | "success" | "denied";

export default function MobileLanding() {
  const [gpsStatus, setGpsStatus] = useState<GpsStatus>("loading");
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const urlParams = new URLSearchParams(window.location.search);
  const isbn = urlParams.get('isbn') || "9788937473135";

  const [bookInfo, setBookInfo] = useState({
    title: "도서 정보 로드 중...",
    author: "조회 중",
    isbn: isbn,
  });

  const fetchBookInfo = async () => {
    try {
      const response = await fetch(`/api/book/${isbn}`);
      if (response.ok) {
        const data = await response.json();
        setBookInfo({
          title: data.title || "가까운 공공도서관 검색",
          author: data.author ? `${data.author} 지음` : "",
          isbn: isbn
        });
      } else {
        setBookInfo({
          title: "도서 안내",
          author: `ISBN: ${isbn}`,
          isbn: isbn
        });
      }
    } catch (e) {
      setBookInfo({
        title: "가까운 공공도서관 검색",
        author: `ISBN: ${isbn}`,
        isbn: isbn
      });
    }
  };

  const fetchLibraries = async (lat: number | null, lng: number | null) => {
    try {
      let url = `/api/locate/${isbn}?region=11&limit=8`;
      if (lat && lng) {
        url += `&lat=${lat}&lng=${lng}`;
      }
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        const libs = (data.libraries || []).map((lib: any) => ({
          name: lib.name,
          address: lib.address,
          distance: lib.distance_km !== undefined ? lib.distance_km : 9999.0,
          available: true, // 대출 가능 소장본
          stock: 1
        }));
        setLibraries(libs);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchBookInfo();
    
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setGpsStatus("success");
          fetchLibraries(position.coords.latitude, position.coords.longitude);
        },
        () => {
          setGpsStatus("denied");
          fetchLibraries(null, null);
        },
        { timeout: 8000 }
      );
    } else {
      setGpsStatus("denied");
      fetchLibraries(null, null);
    }
  }, []);

  const getGpsBadge = () => {
    switch (gpsStatus) {
      case "loading":
        return (
          <Badge className="text-xs font-medium px-3 py-1.5 border" style={{
            background: '#fef9c3',
            color: '#854d0e',
            borderColor: '#fde047',
            borderRadius: '6px'
          }}>
            <SpinnerGap className="animate-spin mr-1.5" size={16} />
            실시간 위치 탐색 중
          </Badge>
        );
      case "success":
        return (
          <Badge className="text-xs font-medium px-3 py-1.5 border" style={{
            background: '#d1fae5',
            color: '#065f46',
            borderColor: '#6ee7b7',
            borderRadius: '6px'
          }}>
            <MapPin className="mr-1.5" size={16} weight="fill" />
            📍 실시간 내 위치 수신 완료
          </Badge>
        );
      case "denied":
        return (
          <Badge className="text-xs font-medium px-3 py-1.5 border" style={{
            background: '#f3f4f6',
            color: '#374151',
            borderColor: '#d1d5db',
            borderRadius: '6px'
          }}>
            <GlobeHemisphereWest className="mr-1.5" size={16} />
            지역 기본 도서관 안내
          </Badge>
        );
    }
  };

  return (
    <div className="min-h-screen" style={{ background: '#faf7f2' }}>
      {/* Section A - Book Info Header Card */}
      <div className="px-5 pt-8 pb-10" style={{
        background: 'linear-gradient(135deg, #1f3d24 0%, #355e3b 100%)',
        color: '#ffffff',
        position: 'relative'
      }}>
        <div className="max-w-md mx-auto">
          {/* Pearl Style Emblem */}
          <div className="flex justify-center mb-4">
            <div className="px-4 py-1.5 rounded-full" style={{
              background: 'rgba(255, 255, 255, 0.15)',
              border: '1px solid rgba(255, 255, 255, 0.25)',
              backdropFilter: 'blur(8px)'
            }}>
              <span style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                letterSpacing: '0.05em'
              }}>BOOK-TIK LIBRARY FINDER</span>
            </div>
          </div>

          <div className="flex items-start justify-between mb-6">
            <div className="flex-1">
              <p style={{
                fontSize: '0.8125rem',
                opacity: 0.80,
                marginBottom: '0.5rem',
                letterSpacing: '0.02em'
              }}>
                숏폼에서 만난 책
              </p>
              <h1 style={{
                fontFamily: '"Noto Serif KR", serif',
                fontSize: '1.5rem',
                fontWeight: 700,
                marginBottom: '0.375rem',
                lineHeight: 1.3
              }}>{bookInfo.title}</h1>
              <p style={{
                fontSize: '0.9375rem',
                opacity: 0.90,
                fontWeight: 500
              }}>{bookInfo.author}</p>
              <p style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '0.6875rem',
                opacity: 0.60,
                marginTop: '0.5rem',
                letterSpacing: '0.03em'
              }}>ISBN: {bookInfo.isbn}</p>
            </div>
            <div className="flex-shrink-0 ml-4">
              <div className="w-16 h-16 rounded-xl flex items-center justify-center" style={{
                background: 'rgba(255, 255, 255, 0.12)',
                border: '2px solid rgba(255, 255, 255, 0.20)'
              }}>
                <BookBookmark size={36} weight="fill" style={{ opacity: 0.90 }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section B - GPS Status Panel */}
      <div className="max-w-md mx-auto px-5 -mt-5 mb-6">
        <Card className="p-4 border rounded-2xl shadow-lg" style={{
          background: '#ffffff',
          borderColor: '#e8e0d4',
          borderRadius: '16px',
          boxShadow: '0 4px 16px rgba(44, 24, 16, 0.08)'
        }}>
          <div className="flex items-center justify-center">
            {getGpsBadge()}
          </div>
        </Card>
      </div>

      {/* Section C - Library Card Stack */}
      <div className="max-w-md mx-auto px-5">
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h2 style={{
              fontFamily: '"Noto Sans KR", sans-serif',
              fontSize: '1.125rem',
              fontWeight: 700,
              color: '#2c1810'
            }}>
              {gpsStatus === "success" ? "최단거리 소장 도서관" : "기본 지역 도서관"}
            </h2>
            {gpsStatus === "success" && (
              <Badge className="text-xs px-2 py-1" style={{
                background: 'rgba(53, 94, 59, 0.10)',
                color: '#355e3b',
                border: 'none',
                borderRadius: '6px'
              }}>
                내 주변 {libraries.length}곳
              </Badge>
            )}
          </div>

          {isLoading ? (
            <>
              {[1, 2, 3].map((i) => (
                <Card key={i} className="p-5 border rounded-2xl" style={{
                  background: '#ffffff',
                  borderColor: '#e8e0d4',
                  borderRadius: '16px',
                  boxShadow: '0 2px 12px rgba(44, 24, 16, 0.06)'
                }}>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-5 w-1/2" style={{ background: 'rgba(44, 24, 16, 0.06)' }} />
                      <Skeleton className="h-6 w-16" style={{ background: 'rgba(44, 24, 16, 0.06)' }} />
                    </div>
                    <Skeleton className="h-4 w-full" style={{ background: 'rgba(44, 24, 16, 0.06)' }} />
                    <Skeleton className="h-4 w-2/3" style={{ background: 'rgba(44, 24, 16, 0.06)' }} />
                  </div>
                </Card>
              ))}
            </>
          ) : libraries.length === 0 ? (
            <div className="text-center py-12">
              <BookBookmark size={56} className="mx-auto mb-4" style={{ color: '#355e3b' }} />
              <h3 style={{
                fontFamily: '"Noto Sans KR", sans-serif',
                fontWeight: 600,
                color: '#2c1810',
                marginBottom: '0.5rem'
              }}>아쉽게도 근처에 소장 도서관이 없어요</h3>
              <p style={{
                fontSize: '0.875rem',
                color: 'rgba(44, 24, 16, 0.60)',
                marginBottom: '1rem'
              }}>검색 범위를 넓혀 확인해 보세요.</p>
              <Button
                variant="outline"
                className="border rounded-xl"
                style={{
                  borderColor: '#355e3b',
                  color: '#355e3b',
                  background: 'transparent',
                  borderRadius: '10px'
                }}
              >
                전국 소장 도서관 보기
              </Button>
            </div>
          ) : (
            libraries.map((library, index) => (
              <Card
                key={index}
                className="p-5 border rounded-2xl cursor-pointer transition-all"
                style={{
                  background: '#ffffff',
                  borderColor: '#e8e0d4',
                  borderRadius: '16px',
                  boxShadow: '0 2px 12px rgba(44, 24, 16, 0.06)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(53, 94, 59, 0.05)';
                  e.currentTarget.style.borderColor = '#355e3b';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(53, 94, 59, 0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#ffffff';
                  e.currentTarget.style.borderColor = '#e8e0d4';
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 2px 12px rgba(44, 24, 16, 0.06)';
                }}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <h3 style={{
                    fontFamily: '"Noto Sans KR", sans-serif',
                    fontWeight: 600,
                    fontSize: '1.0625rem',
                    color: '#2c1810',
                    lineHeight: 1.4
                  }}>{library.name}</h3>
                  <Badge className="text-xs px-2 py-1 font-medium flex-shrink-0 ml-2" style={{
                    background: 'rgba(53, 94, 59, 0.10)',
                    color: '#355e3b',
                    border: 'none',
                    borderRadius: '6px'
                  }}>
                    <MapPin size={12} weight="fill" className="mr-1" />
                    📍 {library.distance}km 앞
                  </Badge>
                </div>

                {/* Address */}
                <p style={{
                  fontSize: '0.9375rem',
                  color: 'rgba(44, 24, 16, 0.60)',
                  lineHeight: 1.65,
                  marginBottom: '1rem'
                }}>{library.address}</p>

                {/* Footer */}
                <div className="flex items-center justify-between pt-3" style={{
                  borderTop: '1px solid rgba(44, 24, 16, 0.08)'
                }}>
                  <div className="flex items-center gap-3">
                    {library.available ? (
                      <>
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full" style={{
                            background: '#2d6a4f',
                            boxShadow: '0 0 6px rgba(45, 106, 79, 0.40)'
                          }}></div>
                          <span style={{
                            fontSize: '0.8125rem',
                            color: '#2d6a4f',
                            fontWeight: 500
                          }}>대출 가능</span>
                        </div>
                        <span style={{
                          fontSize: '0.8125rem',
                          color: 'rgba(44, 24, 16, 0.40)'
                        }}>•</span>
                        <span style={{
                          fontSize: '0.8125rem',
                          color: 'rgba(44, 24, 16, 0.60)'
                        }}>
                          소장: <span style={{ fontWeight: 600, color: '#2c1810' }}>{library.stock}권</span>
                        </span>
                      </>
                    ) : (
                      <Badge className="text-xs px-2 py-1" style={{
                        background: 'rgba(155, 28, 28, 0.10)',
                        color: '#9b1c1c',
                        border: 'none',
                        borderRadius: '6px'
                      }}>
                        대출 불가
                      </Badge>
                    )}
                  </div>

                  <Button
                    size="sm"
                    variant="ghost"
                    className="-mr-2 transition-all"
                    style={{
                      color: '#355e3b',
                      background: 'rgba(53, 94, 59, 0.08)',
                      borderRadius: '8px',
                      fontWeight: 500
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(53, 94, 59, 0.15)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(53, 94, 59, 0.08)';
                    }}
                  >
                    <NavigationArrow size={18} className="mr-1" weight="fill" />
                    🧭 길찾기
                  </Button>
                </div>
              </Card>
            ))
          )}

          {gpsStatus === "denied" && !isLoading && libraries.length > 0 && (
            <Card className="p-4 border rounded-2xl mt-4" style={{
              background: '#f9fafb',
              borderColor: '#e5e7eb',
              borderRadius: '16px'
            }}>
              <div className="flex items-start gap-3">
                <GlobeHemisphereWest size={40} style={{ color: '#9ca3af' }} className="flex-shrink-0" />
                <div style={{ fontSize: '0.875rem', color: 'rgba(44, 24, 16, 0.60)' }}>
                  <p style={{
                    fontWeight: 500,
                    color: '#2c1810',
                    marginBottom: '0.25rem'
                  }}>위치 접근이 차단되어 있어요</p>
                  <p style={{ fontSize: '0.75rem', lineHeight: 1.6 }}>
                    브라우저 설정에서 위치 권한을 허용하시면
                    가장 가까운 도서관을 안내해 드릴 수 있어요.
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-md mx-auto px-5 py-8 mt-8 text-center">
        <div className="mb-3">
          <BookBookmark size={32} style={{ color: '#355e3b', opacity: 0.60 }} className="mx-auto mb-2" />
        </div>
        <p style={{
          fontSize: '0.75rem',
          color: 'rgba(44, 24, 16, 0.40)',
          lineHeight: 1.6
        }}>
          Local Book-Tik Factory<br/>
          AI 기반 지역 맞춤형 북트레일러 자동 생성
        </p>
      </div>
    </div>
  );
}
