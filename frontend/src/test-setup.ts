// Zone.js precisa ser importado ANTES do Angular TestBed (NG0908)
import 'zone.js';
import 'zone.js/testing';

import '@testing-library/jest-dom';
import { getTestBed } from '@angular/core/testing';
import {
  BrowserDynamicTestingModule,
  platformBrowserDynamicTesting,
} from '@angular/platform-browser-dynamic/testing';

// Inicializa o ambiente de teste Angular para o Vitest.
getTestBed().initTestEnvironment(
  BrowserDynamicTestingModule,
  platformBrowserDynamicTesting(),
);
