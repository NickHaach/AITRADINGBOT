import { fetchAnnouncements, fetchHealth, fetchNews } from "@/lib/api";
import { DeskShell } from "@/components/DeskShell";

export default async function HomePage() {
  const [news, health, announcements] = await Promise.all([
    fetchNews(8),
    fetchHealth(),
    fetchAnnouncements(6),
  ]);

  return <DeskShell news={news} announcements={announcements} health={health} />;
}
