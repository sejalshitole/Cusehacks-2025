'use client';
import { faker } from '@faker-js/faker';
import {
  CalendarBody,
  CalendarDate,
  CalendarDatePagination,
  CalendarDatePicker,
  CalendarHeader,
  CalendarItem,
  CalendarMonthPicker,
  CalendarProvider,
  CalendarYearPicker,
} from '@/components/ui/shadcn-io/calendar';
import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';
import { createClient } from '@/lib/supabase/client';

const capitalize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1);
const statuses = [
  { id: faker.string.uuid(), name: 'Planned', color: '#6B7280' },
  { id: faker.string.uuid(), name: 'In Progress', color: '#F59E0B' },
  { id: faker.string.uuid(), name: 'Done', color: '#10B981' },
];

const CalendarWrapper = () => {
  const supabase = createClient();
  const [exampleFeatures, setExampleFeatures] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const fetchUserAndEvents = async () => {
      const { data: { user }, error: userError } = await supabase.auth.getUser();
      if (userError) {
        console.error('Error fetching user:', userError);
        return;
      }
      
      if (user) {
        setUserId(user.id);
        const { data, error } = await supabase.from('calendar_events').select().eq('user_id', user.id);
        if (error) {
          console.error('Error fetching events:', error);
        } else {
          const formattedEvents = data.map((event: any) => ({
            id: event.id,
            name: event.title,
            startAt: new Date(event.start_at),
            endAt: new Date(event.end_at),
            status: statuses[0], // Default status
          }));
          setExampleFeatures(formattedEvents);
        }
      }
    };

    fetchUserAndEvents();
  }, [supabase, userId]);

  const earliestYear =
    exampleFeatures
      .map((feature) => feature.startAt.getFullYear())
      .sort()
      .at(0) ?? new Date().getFullYear();
  const latestYear =
    exampleFeatures
      .map((feature) => feature.endAt.getFullYear())
      .sort()
      .at(-1) ?? new Date().getFullYear();

  const handleCreateEvent = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const title = (form.elements.namedItem('title') as HTMLInputElement).value;
    const description = (form.elements.namedItem('description') as HTMLTextAreaElement).value;
    const location = (form.elements.namedItem('location') as HTMLInputElement).value;
    const start_at = new Date((form.elements.namedItem('start_at') as HTMLInputElement).value).toISOString();
    const end_at = new Date((form.elements.namedItem('end_at') as HTMLInputElement).value).toISOString();
    const all_day = (form.elements.namedItem('all_day') as HTMLInputElement).checked;

    const { data, error } = await supabase
      .from('calendar_events')
      .insert([
        {
          user_id: userId, // Add the user_id here
          title,
          description,
          location,
          start_at,
          end_at,
          all_day,
        },
      ])
      .select();

    if (error) {
      console.error('Error creating event:', error);
    } else if (data) {
      const newFeature = {
        id: data[0].id,
        name: data[0].title,
        startAt: new Date(data[0].start_at),
        endAt: new Date(data[0].end_at),
        status: statuses[0],
      };
      setExampleFeatures([...exampleFeatures, newFeature]);
      setOpen(false);
    }
  };

  return (
    <CalendarProvider>
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>Create Event</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Event</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreateEvent} className="space-y-4">
              <div>
                <Label htmlFor="title">Title</Label>
                <Input id="title" name="title" required />
              </div>
              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea id="description" name="description" />
              </div>
              <div>
                <Label htmlFor="location">Location</Label>
                <Input id="location" name="location" />
              </div>
              <div>
                <Label htmlFor="start_at">Start Date</Label>
                <Input id="start_at" name="start_at" type="datetime-local" required />
              </div>
              <div>
                <Label htmlFor="end_at">End Date</Label>
                <Input id="end_at" name="end_at" type="datetime-local" required />
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox id="all_day" name="all_day" />
                <Label htmlFor="all_day">All day</Label>
              </div>
              <Button type="submit">Create</Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <CalendarDate>
        <CalendarDatePicker>
          <CalendarMonthPicker />
          <CalendarYearPicker end={latestYear} start={earliestYear} />
        </CalendarDatePicker>
        <CalendarDatePagination />
      </CalendarDate>
      <CalendarHeader />
      <CalendarBody features={exampleFeatures}>
        {({ feature }) => <CalendarItem feature={feature} key={feature.id} />}
      </CalendarBody>
    </CalendarProvider>
  );
};
export default CalendarWrapper;