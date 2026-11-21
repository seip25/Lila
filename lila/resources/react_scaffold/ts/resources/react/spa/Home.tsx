import { useState } from "react";
import {
  Badge, Button, Card, Carousel, Checkbox, Drawer, Form, Input, Modal, Select, Skeleton, Spinner, SubmitButton,
  Textarea, toast,
} from "@/components/ui";

// A tour of the UI kit (resources/react/components/ui). Same palette as the Jinja pages.
export default function Home() {
  const [modal, setModal] = useState(false);
  const [drawer, setDrawer] = useState(false);
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-black tracking-tight">Lila UI kit</h1>
        <p className="text-muted-foreground">Edit <code>resources/react/components/ui</code>: the components are your code.</p>
      </div>

      <Card title="Buttons" description="buttonVariants() = the Lila .btn-* classes">
        <div className="flex flex-wrap gap-2">
          {(["primary", "secondary", "outline", "ghost", "danger", "success", "warning", "info", "light", "dark", "link"] as const).map((v) => (
            <Button key={v} variant={v}>{v}</Button>
          ))}
          <Button loading loadingText="Saving...">Save</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Badges & feedback">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>default</Badge>
            <Badge tone="primary">primary</Badge>
            <Badge tone="success" soft>success</Badge>
            <Badge tone="warning" soft>warning</Badge>
            <Badge tone="danger">danger</Badge>
            <Badge tone="info" soft>info</Badge>
            <Spinner className="text-primary" />
          </div>
          <div className="mt-4 space-y-2">
            <Skeleton className="w-2/3" />
            <Skeleton />
          </div>
        </Card>
        <Card title="Toasts, modal and drawer">
          <div className="flex flex-wrap gap-2">
            <Button variant="success" onClick={() => toast.success("Saved", "Your changes are stored.")}>Toast</Button>
            <Button variant="danger" onClick={() => toast.error("Something failed")}>Error toast</Button>
            <Button variant="outline" onClick={() => setModal(true)}>Modal</Button>
            <Button variant="outline" onClick={() => setDrawer(true)}>Drawer</Button>
          </div>
        </Card>
      </div>

      <Card title="Form" description="useForm + Lila 422 errors under each field (this demo posts to a non-existing URL)">
        <Form action="/api/demo" initial={{ name: "", email: "", plan: "pro", bio: "", terms: false }} successToast className="grid gap-4 md:grid-cols-2">
          <Input name="name" label="Name" required />
          <Input name="email" type="email" label="Email" hint="We never share it." required />
          <Select name="plan" label="Plan" options={[{ value: "free", label: "Free" }, { value: "pro", label: "Pro" }]} />
          <Textarea name="bio" label="Bio" wrapperClassName="md:col-span-2" />
          <Checkbox name="terms" label="I accept the terms" />
          <div className="md:col-span-2"><SubmitButton>Send</SubmitButton></div>
        </Form>
      </Card>

      <Carousel
        autoplay={5000}
        slides={[
          { title: "Jinja for SEO pages", description: "Landing pages, blog, docs." },
          { title: "React for apps", description: "Dashboards and admin panels." },
          { title: "Desktop builds", description: ".exe/.msi and .app/.dmg from the same code." },
        ]}
      />

      <Modal open={modal} onClose={() => setModal(false)} title="Modal" description="Native <dialog>: Escape and backdrop close it."
        footer={<><Button variant="outline" onClick={() => setModal(false)}>Cancel</Button><Button onClick={() => setModal(false)}>OK</Button></>}>
        <p>Content goes here.</p>
      </Modal>
      <Drawer open={drawer} onClose={() => setDrawer(false)} title="Drawer" side="right">
        <p>Filters, menus, details...</p>
      </Drawer>
    </div>
  );
}
