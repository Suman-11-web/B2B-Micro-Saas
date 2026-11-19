import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import Link from 'next/link';
import { MessageCircle, Database, BarChart3, Upload, Shield, Clock } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="container mx-auto px-4 py-16">
      {/* Hero Section */}
      <div className="text-center space-y-6 mb-16">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">
            Private AI Document & Data Analyst
          </span>
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Upload your company documents, connect databases, and ask questions in plain English. Get accurate answers with citations, charts, and summaries.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/login">
            <Button size="lg" className="h-12 px-6">Sign In</Button>
          </Link>
          <Link href="/signup">
            <Button variant="outline" size="lg" className="h-12 px-6">Get Started</Button>
          </Link>
        </div>
      </div>

      {/* Features */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
        <Card>
          <CardHeader>
            <CardTitle>Document Upload</CardTitle>
            <CardDescription>PDF, Excel, CSV files with end-to-end encryption</CardDescription>
          </CardHeader>
          <CardContent>
            <Upload className="h-8 w-8 text-primary" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Database Connect</CardTitle>
            <CardDescription>Read-only access to your PostgreSQL, MySQL, or other databases</CardDescription>
          </CardHeader>
          <CardContent>
            <Database className="h-8 w-8 text-primary" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Q&A</CardTitle>
            <CardDescription>Ask questions in plain English, get accurate answers with citations</CardDescription>
          </CardHeader>
          <CardContent>
            <MessageCircle className="h-8 w-8 text-primary" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Statistical Charts</CardTitle>
            <CardDescription>R-powered analysis with custom charts and insights</CardDescription>
          </CardHeader>
          <CardContent>
            <BarChart3 className="h-8 w-8 text-primary" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Enterprise Security</CardTitle>
            <CardDescription>Defense-in-depth encryption, audit logs, and compliance-ready</CardDescription>
          </CardHeader>
          <CardContent>
            <Shield className="h-8 w-8 text-primary" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>24/7 Monitoring</CardTitle>
            <CardDescription>Always-on observability with automated backups and DR</CardDescription>
          </CardHeader>
          <CardContent>
            <Clock className="h-8 w-8 text-primary" />
          </CardContent>
        </Card>
      </div>

      {/* Pricing Preview */}
      <div className="bg-muted rounded-lg p-8">
        <h2 className="text-2xl font-bold text-center mb-6">Pricing</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Starter</CardTitle>
              <CardDescription>$49 / ₹3,000 per month</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm space-y-2">
                <li>✓ 5 GB storage</li>
                <li>✓ 500 queries/month</li>
                <li>✓ Basic charts</li>
              </ul>
            </CardContent>
          </Card>
          <Card className="border-primary">
            <CardHeader>
              <CardTitle>Growth</CardTitle>
              <CardDescription>$99 / ₹7,000 per month</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm space-y-2">
                <li>✓ 20 GB storage</li>
                <li>✓ 2,500 queries/month</li>
                <li>✓ R statistical analysis</li>
                <li>✓ Database connectors</li>
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Business</CardTitle>
              <CardDescription>$199 / ₹15,000 per month</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm space-y-2">
                <li>✓ 100 GB storage</li>
                <li>✓ 10,000 queries/month</li>
                <li>✓ SSO & Audit logs</li>
                <li>✓ Priority support</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}