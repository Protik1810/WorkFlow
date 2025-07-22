# Copyright (C) 2025 Protik Das
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# This file marks the 'ui' directory as a Python package.
# It remains empty as no package-level initialization is required here.

import sys
from pathlib import Path

CONFIG_FILE_NAME = "app_config.json"
DEFAULT_LOGO_PATH = "logo.png"
DEFAULT_ICON_PATH = "logo.ico"

ADMIN_ID = "admin"
ADMIN_PASSCODE = "admin"

SUBFOLDER_NAMES = {
    "departmentDetails": "Department_Documents",
    "departmentEnquiryDetails": "Dept_Enquiry_Docs",
    "oemVendorDetails": "OEM_Vendor_Documents",
    "proposalDocuments": "Proposal_Documents",
    "ceoApprovalDocuments": "CEO_Approval_Documents",
    "workOrderDocuments": "Work_Order_Documents",
    "scopeOfWorkDetails": "Scope_Of_Work_Documents",
    "oenDetails": "OEN_Documents",
    "officeWorkOrderDocuments": "OEN_Documents",
    "fulfillmentDocuments": "Fulfillment_Documents",
    "vendorPayments": "Vendor_Payment_Documents",
    "tenderNoticeDocs": "Tender_Documents/1_Notice",
    "tenderDocs": "Tender_Documents/2_Bidding",
    "limitedTenderBidders": "Limited_Tender_Documents",
    "biddersDocs": "Tender_Documents/3_Bidders",
    "miscDocuments": "Misc_Documents"
}

initial_project_data_template = {
  'projectName': '', 'projectLead': '', 'status': 'PENDING',
  'isTenderProject': False,
  'isLimitedTenderProject': False,
  'departmentDetails': { 'name': '', 'address': '', 'memoId': '', 'memoDate': '', 'documents': [] },
  'departmentEnquiryDetails': {'documents': []},
  'departmentId': None,
  'oemVendorDetails': { 'oemName': '', 'vendorName': '', 'price': '', 'date': '', 'documents': [] },
  'scopeOfWorkDetails': { 'scope': '', 'documents': [] },
  'proposalOrderDetails': {
    'officeProposalId': '', 'proposalDate': '', 'proposalDocuments': [],
    'ceoApprovalDocuments': [],
    'departmentWorkOrderId': '', 'issuingDate': '', 'workOrderDocuments': []
  },
  'billOfMaterials': { 'items': [], 'amountInWords': '' },
  'oenDetails': {
      'oenRegistrationNo': '', 'registrationDate': '', 'officeOenNo': '', 'oenDate': '', 'documents': [],
      'officeWorkOrderId': '', 'officeWorkOrderDate': '', 'officeWorkOrderDocuments': []
  },

  'limitedTenderDetails': {
      'tenderNoticeDocs': [], # <-- ADD THIS LINE
      # MODIFIED: Add a 'docs' key for each bidder
      'bidders': [], # List of {'name': str, 'price': float, 'docs': []}
      'winner': ''   # Name of the winning bidder
  },

  'tenderDetails': {
      'tenderNoticeURL': '',
      'preTenderDocs': [],
      'tenderDocs': [],
      'postTenderDocs': [],
      'bidders': [],
      'qualifiedBidder': '',
      # --- ADDED FOR BID QUALIFICATION ---
      'generalEligibility': [],
      'technicalCompliance': [],
      'marksDistribution': []
  },
  'financialDetails': { 'transactions': [], 'totalPendingInWords': '', 'totalAmountReceived': 0.0, 'totalAmountPending': 0.0 },
  'fulfillmentDocs': {
    'officeTaxInvoice': [],
    'deliveryChallan': [],
    'installationCertificate': [],
    'workCompletionCertificate': []
  },
  'vendorPayments': [],
  'projectFolderPath': '', 'createdAt': '', 'updatedAt': '',
}