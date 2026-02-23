import React from "react";

import { extractApiError } from "../api/client";
import {
  ContractDetail,
  ContractSummary,
  ContractVersionDetail,
  fetchContract,
  fetchContractVersion,
  fetchContracts,
} from "../api/endpoints";
import PageLayout from "../components/layout/PageLayout";
import Card from "../components/ui/Card";
import DataTable from "../components/ui/DataTable";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useI18n } from "../lib/i18n";

function formatDate(value: string | null | undefined, localeTag: string): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(localeTag, { dateStyle: "medium", timeStyle: "short" });
}

export default function ContractsPage() {
  const { locale, localeTag } = useI18n();
  const [contracts, setContracts] = React.useState<ContractSummary[]>([]);
  const [selectedContract, setSelectedContract] = React.useState<ContractDetail | null>(null);
  const [selectedVersion, setSelectedVersion] = React.useState<ContractVersionDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [versionLoading, setVersionLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const selectedContractId = selectedContract?.id ?? null;

  const loadContracts = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchContracts();
      setContracts(response);
      if (!selectedContractId && response.length > 0) {
        const first = response[0];
        const detail = await fetchContract(first.id);
        setSelectedContract(detail);
      }
    } catch (errorResponse) {
      setError(
        extractApiError(
          errorResponse,
          locale === "ru" ? "Не удалось загрузить реестр контрактов." : "Failed to load contracts."
        )
      );
    } finally {
      setLoading(false);
    }
  }, [locale, selectedContractId]);

  const loadContractDetail = React.useCallback(
    async (contractId: string) => {
      setDetailLoading(true);
      setError("");
      setSelectedVersion(null);
      try {
        const detail = await fetchContract(contractId);
        setSelectedContract(detail);
        if (detail.versions.length > 0) {
          const latest = detail.versions[detail.versions.length - 1];
          const version = await fetchContractVersion(contractId, latest.version);
          setSelectedVersion(version);
        }
      } catch (errorResponse) {
        setError(
          extractApiError(
            errorResponse,
            locale === "ru" ? "Не удалось загрузить детали контракта." : "Failed to load contract details."
          )
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [locale]
  );

  const loadVersion = React.useCallback(
    async (contractId: string, version: string) => {
      setVersionLoading(true);
      setError("");
      try {
        const detail = await fetchContractVersion(contractId, version);
        setSelectedVersion(detail);
      } catch (errorResponse) {
        setError(
          extractApiError(
            errorResponse,
            locale === "ru" ? "Не удалось загрузить выбранную версию." : "Failed to load contract version."
          )
        );
      } finally {
        setVersionLoading(false);
      }
    },
    [locale]
  );

  React.useEffect(() => {
    loadContracts();
  }, [loadContracts]);

  return (
    <PageLayout
      title={locale === "ru" ? "Управление контрактами" : "Contract Management"}
      subtitle={
        locale === "ru"
          ? "Версии input-контрактов и схема валидации в режиме чтения."
          : "Versioned input contracts with read-only schema inspection."
      }
      actions={
        <button className="button primary" type="button" onClick={loadContracts} disabled={loading}>
          {loading ? (locale === "ru" ? "Обновление..." : "Refreshing...") : locale === "ru" ? "Обновить" : "Refresh"}
        </button>
      }
    >
      {error ? <ErrorState message={error} /> : null}
      {loading && contracts.length === 0 ? <LoadingState lines={4} /> : null}

      {!loading && contracts.length === 0 ? (
        <EmptyState message={locale === "ru" ? "Контракты не найдены." : "No contracts found."} />
      ) : null}

      {contracts.length > 0 ? (
        <Card title={locale === "ru" ? "Контракты" : "Contracts"} subtitle="YAML-backed contract registry">
          <DataTable>
            <thead>
              <tr>
                <th>ID</th>
                <th>{locale === "ru" ? "Название" : "Name"}</th>
                <th>{locale === "ru" ? "Последняя версия" : "Latest Version"}</th>
                <th>{locale === "ru" ? "Версий" : "Versions"}</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((contract) => (
                <tr
                  key={contract.id}
                  className={contract.id === selectedContractId ? "table-row-active" : ""}
                  onClick={() => loadContractDetail(contract.id)}
                >
                  <td className="mono-small">{contract.id}</td>
                  <td>{contract.name}</td>
                  <td>{contract.latest_version ?? "-"}</td>
                  <td>{contract.versions_count}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </Card>
      ) : null}

      {detailLoading ? <LoadingState lines={3} /> : null}

      {selectedContract ? (
        <Card
          title={selectedContract.name}
          subtitle={selectedContract.description ?? (locale === "ru" ? "Описание отсутствует" : "No description")}
        >
          <div className="panel stack">
            <h4>{locale === "ru" ? "История версий" : "Version History"}</h4>
            <DataTable>
              <thead>
                <tr>
                  <th>{locale === "ru" ? "Версия" : "Version"}</th>
                  <th>{locale === "ru" ? "Дата" : "Date"}</th>
                  <th>{locale === "ru" ? "Изменил" : "Changed By"}</th>
                  <th>{locale === "ru" ? "Изменения" : "Changelog"}</th>
                </tr>
              </thead>
              <tbody>
                {selectedContract.versions.map((version) => (
                  <tr
                    key={version.version}
                    className={selectedVersion?.version === version.version ? "table-row-active" : ""}
                    onClick={() => loadVersion(selectedContract.id, version.version)}
                  >
                    <td className="mono-small">{version.version}</td>
                    <td>{formatDate(version.created_at, localeTag)}</td>
                    <td>{version.changed_by ?? "-"}</td>
                    <td>{version.changelog ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        </Card>
      ) : null}

      {versionLoading ? <LoadingState lines={2} /> : null}

      {selectedVersion ? (
        <Card
          title={locale === "ru" ? `Схема версии ${selectedVersion.version}` : `Schema ${selectedVersion.version}`}
          subtitle={selectedVersion.schema_path}
        >
          <div className="grid-two">
            {Object.entries(selectedVersion.profiles).map(([profileName, profile]) => (
              <div key={profileName} className="panel stack">
                <h4 className="mono-small">{profileName}</h4>
                <p className="muted">
                  {locale === "ru" ? "Обязательные колонки" : "Required columns"}:{" "}
                  {profile.required_columns.join(", ") || "-"}
                </p>
                <p className="muted">{locale === "ru" ? "Типы данных" : "Data types"}</p>
                <DataTable>
                  <thead>
                    <tr>
                      <th>{locale === "ru" ? "Колонка" : "Column"}</th>
                      <th>{locale === "ru" ? "Тип" : "Type"}</th>
                      <th>{locale === "ru" ? "Алиасы" : "Aliases"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(profile.dtypes).map((column) => (
                      <tr key={`${profileName}-${column}`}>
                        <td className="mono-small">{column}</td>
                        <td>{profile.dtypes[column]}</td>
                        <td>{(profile.aliases[column] ?? []).join(", ") || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              </div>
            ))}
          </div>
        </Card>
      ) : null}
    </PageLayout>
  );
}
