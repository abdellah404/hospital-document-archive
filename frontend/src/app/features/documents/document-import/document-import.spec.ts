import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentImport } from './document-import';

describe('DocumentImport', () => {
  let component: DocumentImport;
  let fixture: ComponentFixture<DocumentImport>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DocumentImport],
    }).compileComponents();

    fixture = TestBed.createComponent(DocumentImport);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
