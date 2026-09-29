# Templates in ReframeAI - Complete Guide

## Table of Contents
1. [What Are Templates?](#what-are-templates)
2. [How Templates Work](#how-templates-work)
3. [How to Use Templates](#how-to-use-templates)
4. [Template Use Cases](#template-use-cases)
5. [Where Templates Are Applied](#where-templates-are-applied)
6. [Implementation Opportunities](#implementation-opportunities)

---

## What Are Templates?

**Templates** in your ReframeAI project are **pre-designed visual styling configurations** that control how your AI-generated video clips look. Think of them as professional design presets that instantly transform the appearance of your video captions and overlays.

### What Templates Control

Templates define the visual presentation of your viral clips, including:

- **Caption Styling**: Font family, size, weight, color, positioning
- **Text Effects**: Shadows, outlines, letter spacing, line height
- **Background**: Colors, opacity, border radius, gradients
- **Word Highlighting**: Karaoke-style word-by-word animations
- **Visual Effects**: Vignette, brightness, contrast, saturation
- **Branding**: Logo positioning and watermarks
- **Animations**: Fade, slide, bounce effects for captions

### Current Template Library

Your project currently has **11 professionally designed templates** across 4 categories:

| Category | Count | Examples | Plan Required |
|----------|-------|----------|---------------|
| **Professional** | 3 | Modern Minimal, Elegant Serif, Corporate Clean | Free/Starter |
| **Creative** | 3 | Bold & Energetic, Playful Pop, Retro Vibe | Free/Starter/Pro |
| **Tech** | 2 | Tech Futuristic, Minimalist Dark | Starter/Pro |
| **Lifestyle** | 2 | Warm & Cozy, Fitness Energy | Free/Starter |

### Template Data Structure

Each template is defined in `reframe-ai/src/lib/templates.ts`:

```typescript
interface Template {
  id: string;                    // Unique identifier (e.g., "prof-modern-minimal")
  name: string;                  // Display name (e.g., "Modern Minimal")
  category: string;              // Professional/Creative/Tech/Lifestyle
  description: string;           // What it's good for
  thumbnail: string;             // Preview image URL
  plan: 'Free' | 'Starter' | 'Professional';  // Access tier
  style: TemplateStyle;          // Visual settings (font, colors, etc.)
  tags: string[];                // Searchable keywords
  popular?: boolean;             // Featured template flag
  trending?: boolean;            // Trending template flag
}
```

---

## How Templates Work

### Architecture Overview

Your application has two main components:

```
┌─────────────────────┐         ┌─────────────────────┐
│   reframe-ai (UI)   │         │ opus-clip-cloud     │
│                     │         │ (Video Processing)  │
├─────────────────────┤         ├─────────────────────┤
│ • Templates.tsx     │◄───────►│ • Download          │
│ • TemplateModal     │  API    │ • Transcribe        │
│ • templates.ts      │ Gateway │ • Detect Clips      │
│ • templateCache.ts  │         │ • Process Clip      │
└─────────────────────┘         │ • Finalize          │
                                └─────────────────────┘
```

### Current Workflow

1. **Template Storage**: Templates are defined as static data in `src/lib/templates.ts`
2. **Template Browsing**: Users browse templates in the Templates page (`src/pages/Templates.tsx`)
3. **Template Selection**: Users select templates via a modal (`src/components/TemplateSelectionModal.tsx`)
4. **Template Application**: Currently manual - user selects template for each clip
5. **Template Caching**: Session storage caches templates for performance (`src/lib/templateCache.ts`)

### Video Processing Pipeline Integration Points

Your **opus-clip-cloud** backend processes videos through 6 stages:

```
YouTube URL/Upload
    ↓
[1] Download Video → original_video.mp4
    ↓
[2] Transcribe Audio → transcript.json (with word-level timestamps!)
    ↓
[3] Detect Viral Clips → AI analyzes 3 best clips with virality scores
    ↓
[4] Process Clips → FFmpeg renders 9:16, 16:9, 1:1 with karaoke subtitles
    ↓                  ⚡ TEMPLATE STYLING APPLIED HERE ⚡
[5] Finalize → Generate download URLs
    ↓
[6] Return Results → User sees clips in dashboard
```

**Key Integration Point**: The `process-clip` Lambda function is where templates should be applied. This function:
- Generates ASS (Advanced SubStation Alpha) subtitle files
- Uses FFmpeg to render videos with subtitles
- Creates karaoke-style word-by-word highlighting
- Supports aspect ratio conversion

---

## How to Use Templates

### For End Users

#### Method 1: Browse Templates Page
1. Navigate to **Templates** page from sidebar
2. Browse by category or search by keywords
3. Click on a template to preview
4. System guides you to apply it to clips in your projects

#### Method 2: Apply to Specific Clip
1. Go to **Dashboard** → Select a project
2. Click on a clip you want to style
3. Click **"Apply Template"** button
4. Choose template from modal dialog
5. Template is applied and clip metadata is updated

#### Method 3: Template Selection During Upload (Future)
1. Upload video or paste YouTube URL
2. AI suggests templates based on content analysis
3. Select template before processing
4. All generated clips use chosen template

### For Developers

#### Accessing Templates in Code

```typescript
import {
  templates,           // All templates array
  getTemplateById,     // Get specific template
  getTemplatesByCategory, // Filter by category
  searchTemplates,     // Search by keyword
  canUserAccessTemplate // Check plan access
} from '@/lib/templates';

// Get a specific template
const template = getTemplateById('prof-modern-minimal');

// Filter templates
const professionalTemplates = getTemplatesByCategory('Professional');

// Search templates
const businessTemplates = searchTemplates('business');

// Check user access
const canUse = canUserAccessTemplate(template, userPlan); // userPlan: 'Free' | 'Starter' | 'Professional'
```

#### Template Caching for Performance

```typescript
import { getCachedTemplates, clearTemplateCache } from '@/lib/templateCache';

// Get templates with session storage caching
const templates = getCachedTemplates();

// Clear cache when templates are updated
clearTemplateCache();
```

---

## Template Use Cases

### 1. **Platform-Specific Optimization**

**Problem**: Different social media platforms have different aesthetic requirements.

**Solution**: Create platform-optimized templates.

**Use Cases**:
- **TikTok Template**: Bold captions, bounce animations, TikTok pink highlights
- **YouTube Shorts Template**: Clean, readable captions with YouTube red branding
- **Instagram Reels Template**: Aesthetic gradients, serif fonts, Instagram pink
- **LinkedIn Template**: Professional, corporate blue, business-appropriate styling

**Example**:
```typescript
// TikTok Viral Template
{
  id: 'tiktok-viral',
  name: 'TikTok Viral',
  style: {
    captionFont: 'Montserrat, sans-serif',
    captionFontSize: '48px',
    captionFontWeight: '900',
    highlightColor: '#FE2C55', // TikTok signature pink
    captionAnimation: 'bounce',
    wordByWordAnimation: true,
  }
}
```

### 2. **Content-Type Specific Styling**

**Problem**: Different content types need different visual treatments.

**Solution**: Templates optimized for specific content categories.

**Use Cases**:

#### Podcast Highlights
- Centered text, readable serif font
- Dark overlay for emphasis
- Minimal distractions

#### Educational Content
- High contrast for readability
- Yellow highlight background
- Clean, professional appearance
- No flashy animations

#### Motivational Quotes
- Bold, impactful typography
- Center-aligned, large text
- Dramatic shadows and effects
- Vignette for focus

#### Comedy/Memes
- Impact font (meme-style)
- Top positioning (classic meme format)
- Strong text shadows
- No background boxes

#### Product Reviews
- Clean tech aesthetic
- Logo placement for branding
- Subtle animations
- Professional color schemes

### 3. **Branding & Consistency**

**Problem**: Businesses need consistent branding across all content.

**Solution**: Custom branded templates with company assets.

**Use Cases**:
- **Corporate Communications**: Company colors, logo watermark, consistent font
- **Content Creators**: Personal brand colors, signature style
- **Agencies**: Client-specific branded templates
- **E-commerce**: Product showcase with brand identity

**Implementation Path**:
```typescript
// Custom Brand Template (Future Enhancement)
{
  id: 'custom-brand-acme',
  name: 'ACME Corporation Brand',
  isCustom: true,
  userId: 'user-firebase-id',
  style: {
    captionColor: '#FF6B00',      // Company primary color
    captionBackgroundColor: '#1A1A1A', // Company secondary
    logoUrl: 'users/{uid}/brand/logo.png', // S3/R2 uploaded logo
    logoPosition: 'top-right',
    logoSize: '80px',
  }
}
```

### 4. **Accessibility Compliance**

**Problem**: Some users need high-contrast, easy-to-read captions.

**Solution**: WCAG-compliant accessible templates.

**Use Cases**:
- High contrast (black/white)
- Large text sizes (48px+)
- No animations (for motion sensitivity)
- Simple, readable fonts
- Clear positioning

### 5. **Trend-Based Templates**

**Problem**: Social media trends change rapidly.

**Solution**: Create templates matching current viral styles.

**Use Cases**:
- **Alex Hormozi Style**: High-impact business advice (red background, bold text)
- **Anime Subtitle Style**: Anime-style formatting (popular on TikTok)
- **Mr. Beast Style**: High-energy, attention-grabbing captions
- **Minimalist Apple Style**: Clean, simple, premium aesthetic

### 6. **A/B Testing Visual Styles**

**Problem**: Creators want to know which visual style performs better.

**Solution**: Track template performance across social platforms.

**Use Cases**:
- Test 2-3 templates on same content
- Track engagement rates per template
- Automatically recommend best-performing templates
- Platform-specific performance insights

---

## Where Templates Are Applied

### Frontend (reframe-ai)

#### 1. **Templates Page** (`src/pages/Templates.tsx`)
- **Purpose**: Browse and explore all available templates
- **Features**:
  - Category filtering (All, Professional, Creative, Tech, Lifestyle)
  - Search functionality by name, description, tags
  - Plan-based access control (Free/Starter/Professional)
  - Popular and Trending badges
  - Thumbnail previews
- **User Flow**: Browse → Click → Redirects to Dashboard to apply

#### 2. **Template Selection Modal** (`src/components/TemplateSelectionModal.tsx`)
- **Purpose**: Select template for a specific clip
- **Features**:
  - Modal overlay with template grid
  - Real-time search and filtering
  - Shows currently selected template
  - Plan upgrade prompts for locked templates
  - "Active" badge on selected template
- **User Flow**: Click "Apply Template" on clip → Choose from modal → Apply

#### 3. **Template Definitions** (`src/lib/templates.ts`)
- **Purpose**: Central repository of all template data
- **Contains**:
  - Template interface definitions
  - 11 pre-configured templates
  - Helper functions (getTemplateById, searchTemplates, etc.)
  - CSS generation from template styles
  - Access control logic

#### 4. **Template Caching** (`src/lib/templateCache.ts`)
- **Purpose**: Performance optimization
- **Features**:
  - Session storage caching
  - Version control (cache invalidation)
  - Automatic cache management

#### 5. **Project Details Page** (`src/pages/ProjectDetails.tsx`)
- **Purpose**: Apply templates to clips
- **Current Implementation**:
  - "Apply Template" button on each clip
  - Opens TemplateSelectionModal
  - Updates Firestore with template choice

### Backend (opus-clip-cloud)

Currently, templates are **NOT yet integrated** into the video processing pipeline. Here's where they **should be applied**:

#### 1. **Process Clip Lambda** (`src/process-clip/lambda_function.py`)
**Role**: Primary integration point for template styling

**Current State**:
- Generates ASS subtitle files with fixed styling
- Uses FFmpeg to render videos with subtitles
- Creates karaoke-style word-by-word highlighting

**Template Integration Needed**:
```python
def create_karaoke_ass_with_template(segments, clip_start, output_path, template):
    """
    Generate ASS subtitle file with template styling

    Args:
        segments: Transcript segments with word timestamps
        clip_start: Clip start time
        output_path: Output path for ASS file
        template: Template object with style properties
    """
    # Apply template properties:
    font_name = template['style']['captionFont']
    font_size = template['style']['captionFontSize']
    text_color = hex_to_ass_color(template['style']['captionColor'])
    bg_color = hex_to_ass_color(template['style']['captionBackgroundColor'])
    position = template['style']['captionPosition']  # top/middle/bottom

    # Generate ASS file with template styling
    # ...
```

**FFmpeg Integration**:
```python
# Apply template visual effects
brightness = template['style'].get('brightness', 1.0)
contrast = template['style'].get('contrast', 1.0)
saturation = template['style'].get('saturation', 1.0)

ffmpeg_cmd = [
    'ffmpeg',
    '-i', input_video,
    '-vf', f'eq=brightness={brightness}:contrast={contrast}:saturation={saturation},subtitles={ass_file}',
    '-c:v', 'libx264',
    output_video
]
```

#### 2. **Detect Clips Lambda** (`src/detect-clips/lambda_function.py`)
**Role**: Suggest templates based on content analysis

**Enhancement Needed**:
```python
def analyze_clip_for_templates(transcript_text, virality_scores):
    """
    Analyze clip content and suggest appropriate templates

    Returns:
        suggested_templates: List of template IDs
        category: Content category
    """
    keywords = transcript_text.lower()

    # Content-based suggestions
    if any(word in keywords for word in ['business', 'money', 'entrepreneur']):
        return ['prof-modern-minimal', 'prof-corporate-clean'], 'business'

    elif any(word in keywords for word in ['funny', 'comedy', 'joke']):
        return ['creative-playful-pop', 'creative-bold-energetic'], 'comedy'

    elif any(word in keywords for word in ['learn', 'tutorial', 'how to']):
        return ['prof-elegant-serif', 'prof-modern-minimal'], 'education'

    # Virality-based suggestions
    if virality_scores['hook'] > 85:
        return ['creative-bold-energetic'], 'high-energy'

    return ['prof-modern-minimal'], 'default'
```

#### 3. **Finalize Lambda** (`src/finalize/lambda_function.py`)
**Role**: Store template metadata with results

**Enhancement Needed**:
```python
# Add template information to result.json
result = {
    'clips': [
        {
            'clip_index': 0,
            'title': 'Viral Moment',
            'virality_score': 87,
            'applied_template_id': 'prof-modern-minimal',  # NEW
            'template_applied_at': datetime.now().isoformat(),  # NEW
            'suggested_templates': ['prof-modern-minimal', 'tiktok-viral'],  # NEW
            'download_url': '...'
        }
    ]
}
```

#### 4. **State Machine** (`state-machine.json`)
**Role**: Pass template_id through processing stages

**Enhancement Needed**:
```json
{
  "States": {
    "ProcessClip": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:process-clip",
      "Parameters": {
        "session_id.$": "$.session_id",
        "clip_index.$": "$.clip_index",
        "template_id.$": "$.template_id"  // NEW: Pass template ID
      }
    }
  }
}
```

---

## Implementation Opportunities

### Phase 1: Immediate Enhancements (1-2 Weeks)

#### 1. **Integrate Templates into Video Processing**
**Complexity**: Medium
**Value**: High

**Tasks**:
- Modify `process-clip` Lambda to accept `template_id` parameter
- Load template from shared template definitions
- Apply template styles to ASS subtitle generation
- Apply template FFmpeg filters (brightness, contrast, etc.)
- Update State Machine to pass template_id

**Files to Modify**:
- `opus-clip-cloud/src/process-clip/lambda_function.py`
- `opus-clip-cloud/state-machine.json`
- Share `reframe-ai/src/lib/templates.ts` with backend (convert to JSON)

#### 2. **Add Template Selection Before Processing**
**Complexity**: Low
**Value**: High

**Tasks**:
- Add template selection step to upload flow
- Pass selected template_id to API Gateway
- Store template_id in Firestore session

**Files to Modify**:
- `reframe-ai/src/pages/Upload.tsx` (or wherever upload happens)
- `reframe-ai/src/pages/ProjectDetails.tsx`

#### 3. **Store Applied Templates in Results**
**Complexity**: Low
**Value**: Medium

**Tasks**:
- Update result.json schema to include `applied_template_id`
- Update Firestore document structure
- Display applied template in UI

**Files to Modify**:
- `opus-clip-cloud/src/finalize/lambda_function.py`
- `reframe-ai/src/pages/ProjectDetails.tsx`

### Phase 2: Smart Suggestions (2-3 Weeks)

#### 1. **AI-Powered Template Suggestions**
**Complexity**: Medium
**Value**: Very High

**Tasks**:
- Analyze transcript content in `detect-clips` Lambda
- Match content keywords to template categories
- Use virality scores to suggest styles (high hook = bold templates)
- Return suggested templates in API response

**Implementation**:
```python
# In detect-clips/lambda_function.py
def suggest_templates(clip_data):
    content_analysis = analyze_content(clip_data['text'])
    virality_analysis = analyze_virality(clip_data['scores'])

    # Combine analyses for smart suggestions
    suggestions = match_templates(content_analysis, virality_analysis)

    return suggestions  # ['prof-modern-minimal', 'creative-bold-energetic']
```

#### 2. **Template Recommendation UI**
**Complexity**: Low
**Value**: High

**Tasks**:
- Show "Recommended" badges on suggested templates
- Sort templates by relevance
- Quick-apply recommended template with one click

**Files to Modify**:
- `reframe-ai/src/components/TemplateSelectionModal.tsx`
- `reframe-ai/src/pages/Templates.tsx`

### Phase 3: Advanced Features (1 Month)

#### 1. **Batch Template Application**
**Complexity**: Low
**Value**: Medium

**Feature**: Apply same template to all clips in a project

```typescript
// In ProjectDetails.tsx
const applyTemplateToAllClips = async (templateId: string) => {
  const updates = clips.map(clip =>
    updateDoc(doc(db, 'sessions', sessionId), {
      [`clips.${clip.clipIndex}.templateId`]: templateId,
      [`clips.${clip.clipIndex}.edited`]: true,
    })
  );

  await Promise.all(updates);
  toast.success(`Applied template to all ${clips.length} clips`);
};
```

#### 2. **Custom Branded Templates**
**Complexity**: High
**Value**: Very High (Premium Feature)

**Features**:
- Logo upload functionality
- Brand color picker
- Custom font selection
- Save custom templates per user
- Logo overlay in FFmpeg processing

**Monetization**: Professional plan feature ($29/mo)

#### 3. **Template Performance Analytics**
**Complexity**: High
**Value**: High

**Features**:
- Track template usage per clip
- Collect social media performance data (optional user input)
- Show "Top Performing Templates" dashboard
- Automatic recommendations based on past success

#### 4. **Template Marketplace**
**Complexity**: Very High
**Value**: High (Long-term)

**Features**:
- User-created templates
- Template publishing workflow
- Rating and review system
- Credit-based purchasing
- Revenue sharing (70/30 split)

### Phase 4: Platform-Specific Templates (Ongoing)

**Create specialized template collections**:

1. **TikTok Pack** (10 templates)
   - Viral styles matching current TikTok trends
   - Platform-specific colors and fonts
   - Vertical-optimized layouts

2. **YouTube Shorts Pack** (10 templates)
   - Clean, professional styles
   - YouTube branding colors
   - High readability

3. **Instagram Reels Pack** (10 templates)
   - Aesthetic gradients and filters
   - Instagram-style fonts
   - Story-friendly designs

4. **LinkedIn Pack** (8 templates)
   - Corporate and professional
   - Business-appropriate colors
   - Minimal animations

5. **Podcast Highlight Pack** (8 templates)
   - Conversation-focused
   - Readable serif fonts
   - Minimal distractions

---

## Summary: Key Takeaways

### What Templates Are
- Visual styling presets for video clips
- Control captions, colors, fonts, animations, effects
- 11 templates across 4 categories currently

### How to Use Templates
- **Users**: Browse Templates page → Apply to clips in Dashboard
- **Developers**: Import from `src/lib/templates.ts`, use helper functions

### Template Use Cases
1. Platform-specific optimization (TikTok, YouTube, Instagram, LinkedIn)
2. Content-type styling (education, comedy, business, podcast)
3. Branding & consistency (corporate, personal brand)
4. Accessibility compliance (high contrast, large text)
5. Trend-based styles (viral formats)
6. A/B testing visual styles

### Where Templates Are Applied
- **Frontend**: Templates page, selection modal, caching
- **Backend** (Integration Needed): Process-clip Lambda for ASS generation and FFmpeg rendering

### Implementation Priority
1. ✅ **Immediate**: Integrate templates into video processing pipeline
2. 🎯 **Next**: Smart template suggestions based on content
3. 🚀 **Future**: Custom branding, marketplace, analytics

---

## Next Steps

To fully leverage templates in your project:

1. **Integrate with Video Processing**: Modify `process-clip` Lambda to apply template styles
2. **Enable Template Selection**: Add template picker to upload/processing flow
3. **Build Smart Suggestions**: Add content analysis to recommend templates
4. **Create More Templates**: Expand library with platform-specific collections
5. **Add Custom Branding**: Allow users to upload logos and create branded templates
6. **Track Performance**: Implement analytics to show which templates perform best

Templates are your application's **key differentiator** - they transform basic AI-generated clips into polished, professional content optimized for each platform and content type.
