import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentImportComponent } from './document-import';

describe('DocumentImportComponent', () => {
  let component: DocumentImportComponent;
  let fixture: ComponentFixture<DocumentImportComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DocumentImportComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(DocumentImportComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
