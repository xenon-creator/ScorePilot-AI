import { HeroSection } from "@/components/ui/hero-section-2"
import { AIWorkflow } from "@/components/ui/ai-workflow"
import { ScoringShowcase } from "@/components/ui/scoring-showcase"
import { HumanReview } from "@/components/ui/human-review"
import { AnalyticsSection } from "@/components/ui/analytics-section"
import { Footer } from "@/components/ui/footer"

export default function Home() {
  return (
    <>
      <HeroSection />
      <AIWorkflow />
      <ScoringShowcase />
      <HumanReview />
      <AnalyticsSection />
      <Footer />
    </>
  )
}
